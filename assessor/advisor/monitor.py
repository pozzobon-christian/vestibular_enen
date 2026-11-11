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
    ap.add_argument("cmd", choices=["run", "collect", "analyze", "status", "diag"])
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--query", default="@gustavocerbasi")
    a = ap.parse_args(argv)
    if a.cmd == "diag":
        return diag(a.query)
    db = MonitorDB(DB)
    if a.cmd == "status":
        print(json.dumps(db.summary(), indent=2, ensure_ascii=False)); return 0
    if a.cmd in ("run", "collect"):
        reg = InfluencerRegistry(REGISTRY)
        started = datetime.now(timezone.utc).isoformat()
        n, errors = collect(reg, db)
        wl = json.loads(WATCHLIST.read_text(encoding="utf-8")) if WATCHLIST.exists() else {}
        n += collect_news(db, wl.get("noticias", []), errors)
        update_prices(db, errors)
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
    data = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "usdbrl": usdbrl,
        "resumo": db.summary(),
        "carteira": load_portfolio(db, usdbrl=usdbrl),
        "cotacoes": quotes,
        "campanhas": rep.get("campanhas", []), "grupos": rep.get("grupos_descobertos", []), "lideres": rep.get("lideres", []),
        "autores_mais_ativos": [{"autor": a, "posts": n} for a, n in top_authors],
        "ativos_mais_citados_7d": [{"ticker": t, "mencoes": n} for t, n in top_tickers],
        "posts_recentes": [{"autor": a, "plataforma": pl, "ts": ts, "texto": tx[:200], "url": u, "engajamento": e,
                            "tickers": json.loads(tk or "[]"), "direcao": st} for a, pl, ts, tx, u, e, tk, st in recent_posts],
        "noticias": latest_news(db, 60),
        "estatisticas_autores": db.latest_stats(),
        "erros_ultima_execucao": json.loads((db.conn.execute("SELECT errors FROM runs ORDER BY finished_at DESC LIMIT 1").fetchone() or ["[]"])[0]),
    }
    out.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
    return data



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
