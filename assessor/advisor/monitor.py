"""Ciclo de monitoramento: coleta -> armazena -> cruza com preços -> campanhas
-> sinais -> estatísticas -> exporta. Roda sozinho (GitHub Actions a cada 6h)
ou à mão: `python -m advisor.monitor run`.

Tolerante a falhas: cada fonte que falhar é registrada em `runs.errors` e as
demais continuam. Nunca interrompe por uma fonte fora do ar.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .data.market import fetch_daily_bars, fetch_crypto_daily
from .influencers import (InfluencerRegistry, detect_campaigns, CoMentionGraph, clusters,
                          evaluate_calls, influencer_stats, herd_signal)
from .influencers import collectors
from .storage import MonitorDB
from .news import collect_news, latest_news
from .portfolio.tracker import load_portfolio

REGISTRY = Path("data/influencers.json")
DB = Path("data/monitor.db")
WATCHLIST = Path("data/watchlist.json")


def resolve_youtube_feed(inf, feed: str) -> str:
    """youtube:@handle -> youtube:UC... (tenta handle, depois o nome). Persiste
    no registro para não resolver de novo."""
    cid = feed.split(":", 1)[1]
    if cid.startswith("UC"):
        return cid
    name = inf.name.split("(")[0].strip()
    alt = inf.name[inf.name.find("(") + 1:inf.name.find(")")] if "(" in inf.name else ""
    channel_id = collectors.resolve_youtube_channel(cid, alt, name)
    if not channel_id:
        raise ValueError(f"canal não encontrado para {cid} / {inf.name}")
    inf.feeds = [f"youtube:{channel_id}" if f == feed else f for f in inf.feeds]
    inf.notes = (inf.notes + f" | resolvido: {cid} -> {channel_id}").strip(" |")
    return channel_id


def collect(reg: InfluencerRegistry, db: MonitorDB, sleep: float = 1.5) -> tuple[int, list[str]]:
    total, errors = 0, []
    for inf in reg.all():
        for feed in inf.feeds:
            try:
                if feed.startswith("reddit:"):
                    posts = collectors.reddit_public(feed.split(":", 1)[1])
                elif feed.startswith("telegram:"):
                    posts = collectors.telegram_public_channel(feed.split(":", 1)[1])
                elif feed.startswith("youtube:"):
                    posts = collectors.youtube_channel_uploads(resolve_youtube_feed(inf, feed))
                elif feed.startswith("stocktwits:"):
                    posts = collectors.stocktwits_symbol(feed.split(":", 1)[1])
                elif feed.startswith("x:"):
                    posts = collectors.x_recent_search(f"from:{feed.split(':', 1)[1].lstrip('@')} -is:retweet")
                else:
                    errors.append(f"{inf.key}: feed desconhecido {feed}"); continue
                for p in posts:
                    if not feed.startswith(("reddit:", "stocktwits:")):   # comunidades mantêm o autor real
                        p.author = inf.handle
                    p.platform = inf.platform
                    p.__post_init__()
                n = db.upsert_posts(posts); total += n
                print(f"[ok] {inf.key} {feed}: {len(posts)} posts, {n} novos")
            except Exception as e:  # noqa: BLE001
                msg = f"{inf.key} {feed}: {type(e).__name__}: {str(e)[:160]}"
                errors.append(msg); print(f"[erro] {msg}", file=sys.stderr)
            time.sleep(sleep)
    reg.save()   # persiste channel_ids resolvidos
    return total, errors


def update_prices(db: MonitorDB, errors: list[str]) -> None:
    if not WATCHLIST.exists():
        return
    wl = json.loads(WATCHLIST.read_text(encoding="utf-8"))
    try:   # câmbio para marcar posições em dólar
        bars = fetch_daily_bars("BRL=X", "US")
        db.upsert_prices("USDBRL", "fx", bars[-400:])
    except Exception as e:  # noqa: BLE001
        errors.append(f"cambio USDBRL: {type(e).__name__}: {str(e)[:120]}")
    for coin in wl.get("cripto", []):
        try:
            bars = fetch_crypto_daily(coin)
            sym = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}.get(coin, coin.upper())
            db.upsert_prices(sym, "cripto", bars)
            time.sleep(2)
        except Exception as e:  # noqa: BLE001
            errors.append(f"preco {coin}: {type(e).__name__}: {str(e)[:120]}")
    for sym in wl.get("global", {}):
        try:
            bars = fetch_daily_bars(sym, "US")
            db.upsert_prices(sym, "global", bars[-400:])
            time.sleep(0.4)
        except Exception as e:  # noqa: BLE001
            errors.append(f"preco {sym}: {type(e).__name__}: {str(e)[:120]}")
    for market, tickers in wl.items():
        if market not in ("BR", "US"):
            continue
        for t in tickers:
            try:
                bars = fetch_daily_bars(t, market)
                db.upsert_prices(t, market, bars[-400:])
                time.sleep(0.5)
            except Exception as e:  # noqa: BLE001
                errors.append(f"preco {t}: {type(e).__name__}: {str(e)[:120]}")


def analyze(db: MonitorDB, days: int = 30) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    posts = db.posts_since(since)
    camps = detect_campaigns(posts, window_hours=24, min_authors=3)
    db.save_campaigns(camps)
    tickers = {t for p in posts for t in p.tickers}
    prices = {t: db.closes(t) for t in tickers}
    prices = {t: s for t, s in prices.items() if s}
    all_posts = db.posts_since(datetime.now(timezone.utc) - timedelta(days=400))
    stats = influencer_stats(evaluate_calls(all_posts, prices)) if prices else {}
    if stats:
        db.save_stats(stats)
    stats = stats or db.latest_stats()
    signals = []
    for c in camps:
        s = herd_signal(c, stats)
        db.save_signal(c, s)
        signals.append({**c.summary(), "fase": s.phase, "acao": s.action, "confianca": s.confidence})
    g = CoMentionGraph.from_campaigns(camps)
    report = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "janela_dias": days, "posts_na_janela": len(posts),
        "campanhas": signals, "grupos_descobertos": clusters(g), "lideres": g.leaders()[:15],
        "autores_com_historico": len(stats),
        "resumo_db": db.summary(),
    }
    Path("data/relatorio.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="advisor.monitor")
    ap.add_argument("cmd", choices=["run", "collect", "analyze", "status", "diag", "morning", "short"])
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--query", default="@gustavocerbasi")
    a = ap.parse_args(argv)
    if a.cmd == "diag":
        return diag(a.query)
    db = MonitorDB(DB)
    if a.cmd == "morning":
        print(json.dumps(morning_brief(db), ensure_ascii=False, indent=2, default=str)); return 0
    if a.cmd == "short":
        out = short_ops(db)
        print(json.dumps({k: out[k] for k in ("gerado_em", "setups", "erros")}, ensure_ascii=False, indent=2, default=str)[:6000]); return 0
    if a.cmd == "status":
        print(json.dumps(db.summary(), indent=2, ensure_ascii=False)); return 0
    if a.cmd in ("run", "collect"):
        reg = InfluencerRegistry(REGISTRY)
        started = datetime.now(timezone.utc).isoformat()
        n, errors = collect(reg, db)
        wl = json.loads(WATCHLIST.read_text(encoding="utf-8")) if WATCHLIST.exists() else {}
        n += collect_news(db, wl.get("noticias", []), errors)
        update_prices(db, errors)
        try:
            from .calendar import build_calendar
            wl2 = json.loads(WATCHLIST.read_text(encoding="utf-8"))
            cal = build_calendar([(t, "BR") for t in wl2.get("BR", [])] + [(t, "US") for t in wl2.get("US", [])], errors=errors)
            Path("data/calendario.json").write_text(json.dumps(cal, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            errors.append(f"calendario: {type(e).__name__}: {str(e)[:120]}")
        try:
            errors += short_ops(db)["erros"]
        except Exception as e:  # noqa: BLE001
            errors.append(f"operacoes curtas: {type(e).__name__}: {str(e)[:120]}")
        db.log_run(started, "all", n, errors)
        print(f"coleta: {n} posts novos, {len(errors)} erros")
    if a.cmd in ("run", "analyze"):
        rep = analyze(db, a.days)
        print(json.dumps({k: rep[k] for k in ("posts_na_janela", "campanhas", "grupos_descobertos", "lideres")},
                         ensure_ascii=False, indent=2, default=str)[:4000])
    db.export_jsonl()
    from .report import build
    build(str(DB))
    build_dashboard_data(db)
    return 0


def morning_brief(db: MonitorDB, hours: float = 14.0) -> dict:
    """Briefing global das 6h: o que aconteceu enquanto o Brasil dormia, em números."""
    from .signals import trend_report, news_signals
    wl = json.loads(WATCHLIST.read_text(encoding="utf-8")) if WATCHLIST.exists() else {}
    overnight = []
    for sym, name in wl.get("global", {}).items():
        rows = db.conn.execute("SELECT day, close FROM prices WHERE ticker=? ORDER BY day DESC LIMIT 6", (sym,)).fetchall()
        if len(rows) >= 2:
            overnight.append({"simbolo": sym, "nome": name, "ultimo": round(rows[0][1], 2), "data": rows[0][0],
                              "var_1d": round(rows[0][1] / rows[1][1] - 1, 4),
                              "var_5d": round(rows[0][1] / rows[-1][1] - 1, 4) if len(rows) >= 6 else None})
    trends = []
    for market in ("BR", "US", "cripto"):
        for t in wl.get(market, []):
            sym = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}.get(t, t)
            rows = db.conn.execute("SELECT high, low, close FROM prices WHERE ticker=? ORDER BY day", (sym,)).fetchall()
            if len(rows) < 60:
                continue
            tr = trend_report(sym, [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows])
            trends.append({"ticker": sym, "mercado": market, **tr.__dict__})
    trends.sort(key=lambda x: -x["score"])
    signals = [s.__dict__ | {"evidence": s.evidence.__dict__} for s in news_signals(db, hours)]
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    headlines = db.conn.execute("SELECT published, source, market, title, sentiment, tickers FROM news WHERE published >= ? "
                                "ORDER BY ABS(sentiment) DESC, published DESC LIMIT 25", (since,)).fetchall()
    from .signals import market_regime
    regimes = {}
    for idx in ("BOVA11", "SPY"):
        rows = db.conn.execute("SELECT close FROM prices WHERE ticker=? ORDER BY day", (idx,)).fetchall()
        vix = db.conn.execute("SELECT close FROM prices WHERE ticker='^VIX' ORDER BY day DESC LIMIT 1").fetchone()
        regimes[idx] = market_regime([r[0] for r in rows], vix[0] if vix else None)
    brief = {
        "gerado_em": datetime.now(timezone.utc).isoformat(), "janela_horas": hours,
        "regime": regimes,
        "overnight": overnight, "tendencias": trends, "sinais_de_noticia": signals,
        "manchetes": [{"quando": p, "fonte": s, "mercado": m, "titulo": t, "sentimento": round(sn or 0, 2), "tickers": json.loads(tk or "[]")}
                      for p, s, m, t, sn, tk in headlines],
    }
    Path("data/briefing-6h.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return brief


def short_ops(db: MonitorDB, with_fundamentals: bool = True, with_intraday: bool = True) -> dict:
    """Operações curtas: cruza balanço (público), análogos históricos, notícias
    recentes, tendência e intradia. Grava data/operacoes-curtas.json."""
    from .signals import find_analogs, short_setups, trend_report, news_signals, order_gate, stabilization, structural_stop, crypto_risk_composite, market_regime
    from .signals.intraday import fetch_many as fetch_intra
    from .signals.technical import atr
    from .data.fundamentals_feed import fetch_many as fetch_fund
    from .fundamentals import score_company, ratios
    wl = json.loads(WATCHLIST.read_text(encoding="utf-8")) if WATCHLIST.exists() else {}
    errors: list[str] = []
    CRYPTO = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}
    tickers = [(t, "BR") for t in wl.get("BR", [])] + [(t, "US") for t in wl.get("US", [])] + [(CRYPTO.get(t, t), "cripto") for t in wl.get("cripto", [])]
    equities = [t for t, m in tickers if not t.endswith("11") and m != "cripto"]
    funds = {}
    if with_fundamentals:
        funds.update(fetch_fund([t for t in equities if t in wl.get("BR", [])], "BR", errors))
        funds.update(fetch_fund([t for t in equities if t in wl.get("US", [])], "US", errors))
    intra = {}
    if with_intraday:
        intra.update(fetch_intra([t for t, m in tickers if m == "BR"], "BR", errors))
        intra.update(fetch_intra([t for t, m in tickers if m == "US"], "US", errors))
        for t, m in tickers:
            if m == "cripto":
                try:
                    from .signals.intraday import fetch_intraday
                    intra[t] = fetch_intraday(f"{t}-USD", "US")
                except Exception as e:  # noqa: BLE001
                    errors.append(f"intradia {t}: {type(e).__name__}: {str(e)[:80]}")
    news = {s.ticker: s for s in news_signals(db, hours=24)}
    proxies = {"PETR4": "PBR", "VALE3": "VALE", "ITUB4": "ITUB", "BOVA11": "EWZ", "PRIO3": "BZ=F"}
    # regime e composto de risco cripto, calculados uma vez
    def _closes(sym):
        return [r[0] for r in db.conn.execute("SELECT close FROM prices WHERE ticker=? ORDER BY day", (sym,)).fetchall()]
    vix_row = db.conn.execute("SELECT close FROM prices WHERE ticker='^VIX' ORDER BY day DESC LIMIT 1").fetchone()
    regimes = {"BR": market_regime(_closes("BOVA11"), vix_row[0] if vix_row else None),
               "US": market_regime(_closes("SPY"), vix_row[0] if vix_row else None),
               "cripto": market_regime(_closes("BTC"), vix_row[0] if vix_row else None)}
    def _trend_dir(sym):
        rows = db.conn.execute("SELECT high, low, close FROM prices WHERE ticker=? ORDER BY day", (sym,)).fetchall()
        return trend_report(sym, [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]).direction if len(rows) >= 60 else None
    ibit = _closes("IBIT"); btc = _closes("BTC")
    crypto_risk = crypto_risk_composite(ibit[-1] / ibit[-6] - 1 if len(ibit) > 6 else None, _trend_dir("COIN"), _trend_dir("MSTR"),
                                        btc[-1] if btc else 0.0, min(btc[-20:]) if len(btc) >= 20 else 0.0) if btc else None
    pool = {}
    for t, m in tickers:
        rows = db.conn.execute("SELECT day, high, low, close FROM prices WHERE ticker=? ORDER BY day", (t,)).fetchall()
        if len(rows) >= 230:
            pool[t] = [r[3] for r in rows]
    setups = []
    for t, m in tickers:
        rows = db.conn.execute("SELECT day, high, low, close FROM prices WHERE ticker=? ORDER BY day", (t,)).fetchall()
        if len(rows) < 60:
            continue
        hi, lo, cl, days = [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows], [r[0] for r in rows]
        a = atr(hi, lo, cl)[-1] or 0.0
        tr = trend_report(t, hi, lo, cl)
        an = find_analogs(t, cl, days, extra={k: v for k, v in pool.items() if k != t and (k.endswith("3") or k.endswith("4")) == (t.endswith("3") or t.endswith("4"))}) if len(cl) >= 230 else None
        proxy_move = None
        if t in proxies:
            pr = db.conn.execute("SELECT close FROM prices WHERE ticker=? ORDER BY day DESC LIMIT 2", (proxies[t],)).fetchall()
            if len(pr) == 2 and pr[1][0]:
                proxy_move = pr[0][0] / pr[1][0] - 1
        st = short_setups(t, intra.get(t, []), a, cl[-1] if not intra.get(t) else None, proxy_move) if intra.get(t) else None
        f = funds.get(t)
        fund = None
        if f and f.price and f.shares_outstanding:
            sc = score_company(f); rt = ratios(f)
            fund = {"score": sc.total, "valuation": sc.valuation, "qualidade": sc.quality, "seguranca": sc.safety,
                    "crescimento": sc.growth, "alertas": sc.flags,
                    "P/L": rt["P/L"] and round(rt["P/L"], 1), "EV/EBITDA": rt["EV/EBITDA"] and round(rt["EV/EBITDA"], 1),
                    "ROE": rt["ROE"] and round(rt["ROE"], 3), "div_liq/EBITDA": rt["divida_liquida/EBITDA"] and round(rt["divida_liquida/EBITDA"], 2),
                    "FCF_yield": rt["FCF_yield"] and round(rt["FCF_yield"], 3), "fonte": f.notes}
        ns = news.get(t)
        # cruzamento: cada camada vota; só vira candidato com 2+ camadas a favor e nenhuma forte contra
        votes = {"balanco": None, "analogos": None, "noticias": None, "tendencia": None, "intradia": None}
        if fund: votes["balanco"] = "a_favor" if fund["score"] >= 60 else "contra" if fund["score"] < 40 else "neutro"
        if an and 20 in an.horizons:
            h = an.horizons[20]; votes["analogos"] = "a_favor" if h["p_positivo"] >= 0.65 and h["mediana"] > 0.01 else "contra" if h["p_positivo"] <= 0.35 and h["mediana"] < -0.01 else "neutro"
        if ns: votes["noticias"] = "a_favor" if ns.action == "compra" else "contra" if ns.action == "venda" else "neutro"
        votes["tendencia"] = "a_favor" if tr.direction == "alta" and tr.score >= 50 else "contra" if tr.direction == "baixa" and tr.score >= 50 else "neutro"
        if st: votes["intradia"] = "a_favor" if st.direction == "compra" else "contra" if st.direction == "venda" else "neutro"
        fav = sum(1 for v in votes.values() if v == "a_favor"); con = sum(1 for v in votes.values() if v == "contra")
        side = "compra" if fav >= 2 and con == 0 else "venda" if con >= 2 and fav == 0 else "nenhuma"
        last = cl[-1]
        stop = target = None
        gate = None
        if side != "nenhuma":
            stab = stabilization(hi, lo, cl, side)
            gate = order_gate(side, votes, tr.direction, tr.score, regimes.get(m, {}).get("modo", "neutro"), stab,
                              an.n if an else None, crypto_risk if m == "cripto" else None, vix=vix_row[0] if vix_row else None)
            stop = structural_stop(lo, hi, cl, a, side)
            risk_unit = abs(last - stop)
            target = round(last + 2 * risk_unit, 2) if side == "compra" else round(last - 2 * risk_unit, 2)
            if not gate.approved:
                side = f"{side}_bloqueada"
        setups.append({
            "ticker": t, "mercado": m, "ultimo": round(last, 4), "atr": round(a, 4),
            "operacao": side, "votos": votes, "a_favor": fav, "contra": con,
            "stop": stop, "alvo": target, "porteiro": gate.as_dict() if gate else None,
            "ganho_pct": round((target / last - 1) if target else 0, 4), "risco_pct": round((stop / last - 1) if stop else 0, 4),
            "razao_ganho_risco": 2.0 if side in ("compra", "venda") else None, "prazo_esperado": "1 a 5 pregões" if side in ("compra", "venda") else None,
            "balanco": fund, "analogos": (an.__dict__ | {"state": None}) if an else None,
            "noticia": ({"acao": ns.action, "score": ns.score, "fontes": ns.n_sources, "manchetes": ns.headlines[:2], "evidencia": ns.reasons} if ns else None),
            "tendencia": {"direcao": tr.direction, "score": tr.score, "tstat": tr.tstat, "adx": tr.adx, "rompimento": tr.breakout},
            "intradia": st.__dict__ if st else None,
        })
    setups.sort(key=lambda x: (-(x["a_favor"] - x["contra"]) if x["operacao"] == "compra" else -(x["contra"] - x["a_favor"]) if x["operacao"] == "venda" else 1, x["ticker"]))
    out = {"gerado_em": datetime.now(timezone.utc).isoformat(), "setups": setups, "erros": errors,
           "regimes": regimes, "risco_cripto": crypto_risk,
           "ordens_planejadas": gate_planned_orders(db, regimes, crypto_risk, {x["ticker"]: x for x in setups})}
    Path("data/operacoes-curtas.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return out


def gate_planned_orders(db: MonitorDB, regimes: dict, crypto_risk: dict | None, setups: dict | None = None) -> list[dict]:
    """Passa cada ordem planejada em carteira.json pelo porteiro de tese e grava o veredito."""
    from .signals import trend_report, find_analogs, order_gate, stabilization, structural_stop
    from .signals.technical import atr
    path = Path("data/carteira.json")
    if not path.exists():
        return []
    c = json.loads(path.read_text(encoding="utf-8"))
    plano = json.loads(Path("data/plano.json").read_text(encoding="utf-8")) if Path("data/plano.json").exists() else {}
    cap = float(plano.get("capital_inicial_brl", 0) or 0); lim = cap * float((plano.get("risco") or {}).get("por_operacao", 0.02))
    out = []
    for o in c.get("ordens_planejadas", []):
        t = o["ticker"]
        rows = db.conn.execute("SELECT high, low, close FROM prices WHERE ticker=? ORDER BY day", (t,)).fetchall()
        if len(rows) < 60:
            o["porteiro"] = {"aprovada": None, "motivos": ["sem histórico suficiente"], "bloqueios": []}; out.append(o); continue
        hi, lo, cl = [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]
        tr = trend_report(t, hi, lo, cl); an = find_analogs(t, cl, k=15) if len(cl) >= 230 else None
        side = "compra" if str(o.get("lado", "")).lower() in ("buy", "compra") else "venda"
        votes = {"tendencia": "a_favor" if tr.direction == side.replace("compra", "alta").replace("venda", "baixa") and tr.score >= 50
                 else "contra" if tr.direction in ("alta", "baixa") and tr.score >= 50 else "neutro",
                 "analogos": None, "balanco": None, "noticias": None, "intradia": None}
        if an and 20 in an.horizons:
            h = an.horizons[20]; votes["analogos"] = "a_favor" if h["p_positivo"] >= 0.65 and h["mediana"] > 0.01 else "contra" if h["p_positivo"] <= 0.35 else "neutro"
        su = (setups or {}).get(t)
        if su:   # reaproveita balanço, notícias e intradia calculados no cruzamento
            for k in ("balanco", "noticias", "intradia"):
                if su["votos"].get(k) is not None:
                    votes[k] = su["votos"][k]
        if o.get("tese_manual_camadas"):
            votes.update(o["tese_manual_camadas"])
        stab = stabilization(hi, lo, cl, side)
        m = o.get("mercado", "BR")
        vix_row = db.conn.execute("SELECT close FROM prices WHERE ticker='^VIX' ORDER BY day DESC LIMIT 1").fetchone()
        g = order_gate(side, votes, tr.direction, tr.score, regimes.get(m, {}).get("modo", "neutro"), stab,
                       an.n if an else None, crypto_risk if m == "cripto" else None, o.get("risco_brl"), lim or None,
                       vix=vix_row[0] if vix_row else None)
        a = atr(hi, lo, cl)[-1] or 0.0
        g.structural_stop = structural_stop(lo, hi, cl, a, side)
        o["porteiro"] = g.as_dict() | {"votos": votes, "tendencia": f"{tr.direction} {tr.score}", "ultimo": round(cl[-1], 4)}
        out.append(o)
    c["ordens_planejadas"] = out
    path.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def build_dashboard_data(db: MonitorDB, out: Path = Path("data/dashboard-data.json")) -> dict:
    """Um único JSON com tudo que a interface mostra."""
    rep = json.loads(Path("data/relatorio.json").read_text(encoding="utf-8")) if Path("data/relatorio.json").exists() else {}
    fx_row = db.conn.execute("SELECT close FROM prices WHERE ticker='USDBRL' ORDER BY day DESC LIMIT 1").fetchone()
    usdbrl = fx_row[0] if fx_row else None
    wl = json.loads(WATCHLIST.read_text(encoding="utf-8")) if WATCHLIST.exists() else {}
    quotes = []
    for market, tickers in wl.items():
        if market not in ("BR", "US", "cripto"):
            continue
        for t in tickers:
            sym = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}.get(t, t)
            rows = db.conn.execute("SELECT day, close FROM prices WHERE ticker=? ORDER BY day DESC LIMIT 30", (sym,)).fetchall()
            if not rows:
                continue
            closes = [r[1] for r in rows]
            quotes.append({"ticker": sym, "mercado": market, "ultimo": round(closes[0], 4), "data": rows[0][0],
                           "var_1d": round(closes[0] / closes[1] - 1, 4) if len(closes) > 1 else None,
                           "var_5d": round(closes[0] / closes[5] - 1, 4) if len(closes) > 5 else None,
                           "var_20d": round(closes[0] / closes[20] - 1, 4) if len(closes) > 20 else None,
                           "serie": list(reversed(closes))})
    top_authors = db.conn.execute("SELECT author_key, COUNT(*) n FROM posts GROUP BY author_key ORDER BY n DESC LIMIT 20").fetchall()
    top_tickers = db.conn.execute("SELECT t.value, COUNT(*) n FROM posts, json_each(posts.tickers) t "
                                  "WHERE posts.ts >= datetime('now','-7 days') GROUP BY t.value ORDER BY n DESC LIMIT 15").fetchall()
    recent_posts = db.conn.execute("SELECT author_key, platform, ts, text, url, engagement, tickers, stance FROM posts "
                                   "ORDER BY ts DESC LIMIT 40").fetchall()
    reg = InfluencerRegistry(REGISTRY)
    author_links = {}
    for inf in reg.all():
        h = inf.handle.lstrip("@")
        url = {"youtube": f"https://www.youtube.com/{inf.handle if inf.handle.startswith('@') else '@' + h}",
               "x": f"https://x.com/{h}", "reddit": f"https://www.reddit.com/r/{h}", "telegram": f"https://t.me/{h}",
               "instagram": f"https://www.instagram.com/{h}", "stocktwits": "https://stocktwits.com"}.get(inf.platform, "")
        author_links[inf.key] = {"nome": inf.name or inf.handle, "url": url}
    data = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "usdbrl": usdbrl,
        "autores_links": author_links,
        "resumo": db.summary(),
        "carteira": load_portfolio(db, usdbrl=usdbrl),
        "cotacoes": quotes,
        "campanhas": rep.get("campanhas", []), "grupos": rep.get("grupos_descobertos", []), "lideres": rep.get("lideres", []),
        "autores_mais_ativos": [{"autor": a, "posts": n} for a, n in top_authors],
        "ativos_mais_citados_7d": [{"ticker": t, "mencoes": n} for t, n in top_tickers],
        "posts_recentes": [{"autor": a, "plataforma": pl, "ts": ts, "texto": tx[:200], "url": u, "engajamento": e,
                            "tickers": json.loads(tk or "[]"), "direcao": st} for a, pl, ts, tx, u, e, tk, st in recent_posts],
        "noticias": latest_news(db, 60),
        "briefing_6h": {k: v for k, v in morning_brief(db).items() if k in ("overnight", "tendencias", "sinais_de_noticia", "regime")},
        "estado_24h": (json.loads(Path("data/estado-24h.json").read_text(encoding="utf-8")) if Path("data/estado-24h.json").exists() else {}),
        "estrategias_10_anos": (json.loads(Path("data/cases/estrategias-10-anos.json").read_text(encoding="utf-8")) if Path("data/cases/estrategias-10-anos.json").exists() else {}),
        "calendario": (json.loads(Path("data/calendario.json").read_text(encoding="utf-8")) if Path("data/calendario.json").exists() else []),
        "operacoes_curtas": (json.loads(Path("data/operacoes-curtas.json").read_text(encoding="utf-8")) if Path("data/operacoes-curtas.json").exists() else {}),
        "estatisticas_autores": db.latest_stats(),
        "erros_ultima_execucao": json.loads((db.conn.execute("SELECT errors FROM runs ORDER BY finished_at DESC LIMIT 1").fetchone() or ["[]"])[0]),
    }
    out.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
    build_embedded_dashboard(out)
    return data


def build_embedded_dashboard(data_path: Path = Path("data/dashboard-data.json"),
                             template: Path = Path("dashboard/index.html"),
                             out: Path = Path("dashboard/painel.html")) -> Path:
    """Página autossuficiente: dados embutidos, abre em qualquer lugar sem rede."""
    if not template.exists() or not data_path.exists():
        return out
    payload = data_path.read_text(encoding="utf-8").replace("</script", "<\\/script")
    html = template.read_text(encoding="utf-8").replace(
        "</head>", f'<script id="data" type="application/json">{payload}</script>\n</head>', 1)
    out.write_text(html, encoding="utf-8")
    return out



def diag(query: str) -> int:
    """Mostra o que o YouTube devolve ao runner para um handle/nome."""
    import requests
    from .influencers.collectors import _YT_HEADERS, _YT_EXTERNAL, _YT_CANON, _YT_ANY, _YT_SEARCH
    for url, params in ((f"https://www.youtube.com/{query}", None),
                        ("https://www.youtube.com/results", {"search_query": query.lstrip("@"), "sp": "EgIQAg%3D%3D"}),
                        ("https://www.youtube.com/feeds/videos.xml", {"channel_id": "UCtbxlqGhUONVl9LI0cJKlgQ"})):
        for hdr_name, hdr in (("yt_headers", _YT_HEADERS), ("simples", {"User-Agent": "Mozilla/5.0"})):
            try:
                r = requests.get(url, params=params, headers=hdr, timeout=20, allow_redirects=True)
                body = r.text
                print(f"{url} [{hdr_name}] -> {r.status_code} final={r.url} len={len(body)}")
                print("   externalId:", _YT_EXTERNAL.findall(body)[:3], "canonical:", _YT_CANON.findall(body)[:2],
                      "any:", _YT_ANY.findall(body)[:3], "search:", _YT_SEARCH.findall(body)[:3],
                      "entry:", "<entry>" in body, "consent:", "consent.youtube.com" in r.url or "consent" in body[:3000].lower())
                print("   trecho:", body[:300].replace("\n", " "))
            except Exception as e:  # noqa: BLE001
                print(f"{url} [{hdr_name}] ERRO {type(e).__name__}: {e}")
    # estrutura da página /videos (layout muda; medir as chaves presentes)
    for cid in ("UCtbxlqGhUONVl9LI0cJKlgQ", "UCCE-jo1GvBJqyj1b287h7jA"):
        r = requests.get(f"https://www.youtube.com/channel/{cid}/videos", headers=_YT_HEADERS, timeout=20)
        body = r.text
        keys = ["videoRenderer", "richItemRenderer", "lockupViewModel", "contentId", "videoId", "shortsLockupViewModel",
                "publishedTimeText", "metadataParts", "lockupMetadataViewModel", "ytInitialData", "richGridRenderer"]
        print(f"/videos {cid} -> {r.status_code} len={len(body)} ", {k: body.count(k) for k in keys})
        for key in ("\"lockupMetadataViewModel\"", "\"metadataParts\"", "\"videoRenderer\""):
            i = body.find(key)
            if i >= 0:
                print(f"   contexto {key}:", body[i:i + 700].replace("\n", " "))
        from .influencers.collectors import _parse_lockups
        print("   lockups parseados:", _parse_lockups(body, 5))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
