"""Ciclo de monitoramento: coleta -> armazena -> cruza com preços -> campanhas
-> sinais -> estatísticas -> exporta. Roda sozinho (GitHub Actions a cada 6h)
ou à mão: `python -m advisor.monitor run`.

Tolerante a falhas: cada fonte que falhar é registrada em `runs.errors` e as
demais continuam. Nunca interrompe por uma fonte fora do ar.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .data.market import fetch_daily_bars
from .influencers import (InfluencerRegistry, detect_campaigns, CoMentionGraph, clusters,
                          evaluate_calls, influencer_stats, herd_signal)
from .influencers import collectors
from .storage import MonitorDB

REGISTRY = Path("data/influencers.json")
DB = Path("data/monitor.db")
WATCHLIST = Path("data/watchlist.json")


def resolve_youtube_channel_id(handle_or_url: str) -> str | None:
    """Converte @handle ou URL em channel_id (UC...). Precisa de rede."""
    import requests
    url = handle_or_url if handle_or_url.startswith("http") else f"https://www.youtube.com/{handle_or_url}"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 assessor-investimentos/0.1"}, timeout=20)
    r.raise_for_status()
    m = re.search(r'"channelId":"(UC[^"]+)"', r.text) or re.search(r'youtube\.com/channel/(UC[^"/?]+)', r.text)
    return m.group(1) if m else None


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
                    cid = feed.split(":", 1)[1]
                    if not cid.startswith("UC"):
                        cid = resolve_youtube_channel_id(cid) or cid
                    posts = collectors.youtube_channel_uploads(cid)
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
    return total, errors


def update_prices(db: MonitorDB, errors: list[str]) -> None:
    if not WATCHLIST.exists():
        return
    wl = json.loads(WATCHLIST.read_text(encoding="utf-8"))
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
    ap.add_argument("cmd", choices=["run", "collect", "analyze", "status"])
    ap.add_argument("--days", type=int, default=30)
    a = ap.parse_args(argv)
    db = MonitorDB(DB)
    if a.cmd == "status":
        print(json.dumps(db.summary(), indent=2, ensure_ascii=False)); return 0
    if a.cmd in ("run", "collect"):
        reg = InfluencerRegistry(REGISTRY)
        started = datetime.now(timezone.utc).isoformat()
        n, errors = collect(reg, db)
        update_prices(db, errors)
        db.log_run(started, "all", n, errors)
        print(f"coleta: {n} posts novos, {len(errors)} erros")
    if a.cmd in ("run", "analyze"):
        rep = analyze(db, a.days)
        print(json.dumps({k: rep[k] for k in ("posts_na_janela", "campanhas", "grupos_descobertos", "lideres")},
                         ensure_ascii=False, indent=2, default=str)[:4000])
    db.export_jsonl()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
