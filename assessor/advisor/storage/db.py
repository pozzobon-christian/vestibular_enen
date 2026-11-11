"""Armazenamento em SQLite de tudo que o monitor coleta e calcula.

Um arquivo (`data/monitor.db`) com: posts, preços, campanhas detectadas,
sinais de boiada, chamadas avaliadas e estatísticas por influenciador.
É o ponto de cruzamento entre influenciadores, preços, sentimento e risco.

Exportações JSONL em `data/exports/` ficam versionadas no git para auditoria
e para análise fora do SQLite.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

from ..influencers.posts import Post

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,            -- url ou hash(author+ts+text)
    author_key TEXT NOT NULL,
    platform TEXT NOT NULL,
    ts TEXT NOT NULL,               -- ISO UTC
    text TEXT NOT NULL,
    url TEXT,
    engagement INTEGER DEFAULT 0,
    tickers TEXT,                   -- JSON list
    stance TEXT,
    collected_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_posts_ts ON posts(ts);
CREATE INDEX IF NOT EXISTS ix_posts_author ON posts(author_key);

CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL, market TEXT NOT NULL, day TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (ticker, market, day)
);

CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,            -- ticker|stance|start
    ticker TEXT, stance TEXT, start TEXT, end TEXT,
    n_authors INTEGER, leader TEXT, authors TEXT, reach INTEGER, n_posts INTEGER,
    detected_at TEXT
);

CREATE TABLE IF NOT EXISTS herd_signals (
    campaign_id TEXT, computed_at TEXT, phase TEXT, action TEXT, confidence REAL, reasons TEXT,
    PRIMARY KEY (campaign_id, computed_at)
);

CREATE TABLE IF NOT EXISTS influencer_stats (
    author_key TEXT, computed_at TEXT, stats TEXT,
    PRIMARY KEY (author_key, computed_at)
);

CREATE TABLE IF NOT EXISTS runs (
    started_at TEXT PRIMARY KEY, finished_at TEXT, source TEXT, n_posts INTEGER, errors TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MonitorDB:
    def __init__(self, path: Path | str = "data/monitor.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)

    # ---- posts ----------------------------------------------------------
    @staticmethod
    def post_id(p: Post) -> str:
        if p.url:
            return p.url
        import hashlib
        return hashlib.sha1(f"{p.author_key}|{p.ts.isoformat()}|{p.text}".encode()).hexdigest()

    def upsert_posts(self, posts: list[Post]) -> int:
        rows = [(self.post_id(p), p.author_key, p.platform, p.ts.astimezone(timezone.utc).isoformat(),
                 p.text, p.url, p.engagement, json.dumps(p.tickers), p.stance, _now()) for p in posts]
        cur = self.conn.executemany(
            "INSERT OR IGNORE INTO posts VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
        self.conn.commit()
        return cur.rowcount

    def posts_since(self, since: datetime) -> list[Post]:
        cur = self.conn.execute(
            "SELECT author_key, platform, ts, text, url, engagement, tickers, stance FROM posts WHERE ts >= ? ORDER BY ts",
            (since.astimezone(timezone.utc).isoformat(),))
        out = []
        for a, pl, ts, text, url, eng, tickers, stance in cur.fetchall():
            out.append(Post(author=a, platform=pl, ts=datetime.fromisoformat(ts), text=text, url=url or "",
                            engagement=eng or 0, tickers=json.loads(tickers or "[]"), stance=stance or ""))
        return out

    # ---- prices ---------------------------------------------------------
    def upsert_prices(self, ticker: str, market: str, bars) -> int:
        rows = [(ticker, market, b.day.isoformat(), b.open, b.high, b.low, b.close, b.volume) for b in bars]
        cur = self.conn.executemany("INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?,?)", rows)
        self.conn.commit()
        return cur.rowcount

    def closes(self, ticker: str) -> list[tuple[date, float]]:
        cur = self.conn.execute("SELECT day, close FROM prices WHERE ticker=? ORDER BY day", (ticker,))
        return [(date.fromisoformat(d), c) for d, c in cur.fetchall()]

    # ---- análises -------------------------------------------------------
    def save_campaigns(self, campaigns) -> None:
        rows = [(f"{c.ticker}|{c.stance}|{c.start.isoformat()}", c.ticker, c.stance, c.start.isoformat(),
                 c.end.isoformat(), c.n_authors, c.leader, json.dumps(c.authors), c.reach, len(c.posts), _now())
                for c in campaigns]
        self.conn.executemany("INSERT OR REPLACE INTO campaigns VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        self.conn.commit()

    def save_signal(self, campaign, signal) -> None:
        cid = f"{campaign.ticker}|{campaign.stance}|{campaign.start.isoformat()}"
        self.conn.execute("INSERT OR REPLACE INTO herd_signals VALUES (?,?,?,?,?,?)",
                          (cid, _now(), signal.phase, signal.action, signal.confidence, json.dumps(signal.reasons, ensure_ascii=False)))
        self.conn.commit()

    def save_stats(self, stats: dict[str, dict]) -> None:
        now = _now()
        self.conn.executemany("INSERT OR REPLACE INTO influencer_stats VALUES (?,?,?)",
                              [(a, now, json.dumps(s, ensure_ascii=False)) for a, s in stats.items()])
        self.conn.commit()

    def latest_stats(self) -> dict[str, dict]:
        cur = self.conn.execute(
            "SELECT author_key, stats FROM influencer_stats s WHERE computed_at = "
            "(SELECT MAX(computed_at) FROM influencer_stats WHERE author_key = s.author_key)")
        return {a: json.loads(s) for a, s in cur.fetchall()}

    def log_run(self, started_at: str, source: str, n_posts: int, errors: list[str]) -> None:
        self.conn.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?)",
                          (started_at, _now(), source, n_posts, json.dumps(errors, ensure_ascii=False)))
        self.conn.commit()

    # ---- export ---------------------------------------------------------
    def export_jsonl(self, out_dir: Path | str = "data/exports") -> dict[str, int]:
        out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
        counts = {}
        for table in ("posts", "campaigns", "herd_signals", "influencer_stats", "runs"):
            cur = self.conn.execute(f"SELECT * FROM {table}")
            cols = [d[0] for d in cur.description]
            n = 0
            with (out / f"{table}.jsonl").open("w", encoding="utf-8") as f:
                for row in cur.fetchall():
                    f.write(json.dumps(dict(zip(cols, row)), ensure_ascii=False) + "\n"); n += 1
            counts[table] = n
        return counts

    def summary(self) -> dict:
        q = lambda s: self.conn.execute(s).fetchone()[0]
        return {
            "posts": q("SELECT COUNT(*) FROM posts"),
            "autores": q("SELECT COUNT(DISTINCT author_key) FROM posts"),
            "campanhas": q("SELECT COUNT(*) FROM campaigns"),
            "sinais": q("SELECT COUNT(*) FROM herd_signals"),
            "precos": q("SELECT COUNT(*) FROM prices"),
            "ultima_execucao": q("SELECT MAX(finished_at) FROM runs"),
        }
