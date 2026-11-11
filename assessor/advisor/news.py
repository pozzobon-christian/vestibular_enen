"""Coleta de notícias (RSS) para a tabela `news`, com sentimento por léxico."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .data.market import fetch_rss
from .influencers.posts import extract_tickers
from .signals.sentiment import score_text

SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    url TEXT PRIMARY KEY, source TEXT, kind TEXT, market TEXT, title TEXT, summary TEXT,
    published TEXT, tickers TEXT, sentiment REAL, collected_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_news_pub ON news(published);
"""


def _parse_date(text: str) -> str:
    if not text:
        return datetime.now(timezone.utc).isoformat()
    try:
        return parsedate_to_datetime(text).astimezone(timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except Exception:  # noqa: BLE001
            return datetime.now(timezone.utc).isoformat()


def collect_news(db, feeds: list[dict], errors: list[str], sleep: float = 1.0) -> int:
    db.conn.executescript(SCHEMA)
    total = 0
    for f in feeds:
        try:
            items = fetch_rss(f["url"], limit=40)
            rows = []
            for it in items:
                if not it["link"]:
                    continue
                text = f"{it['title']} {it['summary']}"
                rows.append((it["link"], f["nome"], f.get("fonte", "imprensa"), f.get("mercado", ""), it["title"],
                             it["summary"][:600], _parse_date(it["published"]), json.dumps(extract_tickers(text)),
                             score_text(text), datetime.now(timezone.utc).isoformat()))
            cur = db.conn.executemany("INSERT OR IGNORE INTO news VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
            db.conn.commit()
            total += cur.rowcount
            print(f"[ok] noticias {f['nome']}: {len(rows)} itens, {cur.rowcount} novos")
        except Exception as e:  # noqa: BLE001
            errors.append(f"noticias {f['nome']}: {type(e).__name__}: {str(e)[:120]}")
        time.sleep(sleep)
    return total


def latest_news(db, limit: int = 60) -> list[dict]:
    db.conn.executescript(SCHEMA)
    cur = db.conn.execute("SELECT url, source, kind, market, title, published, tickers, sentiment FROM news "
                          "ORDER BY published DESC LIMIT ?", (limit,))
    return [dict(url=u, fonte=s, tipo=k, mercado=m, titulo=t, publicado=p, tickers=json.loads(tk or "[]"),
                 sentimento=round(sen or 0, 3)) for u, s, k, m, t, p, tk, sen in cur.fetchall()]
