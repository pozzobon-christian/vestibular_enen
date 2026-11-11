"""Coletores de posts públicos. Cada função devolve list[Post].

- reddit_public: JSON público de subreddits (sem chave; respeitar rate limit ~1 req/2s).
- telegram_public_channel: prévia pública de canais abertos (t.me/s/<canal>).
- x_recent_search: API v2 (precisa de X_BEARER_TOKEN no ambiente).
- youtube_channel_uploads: RSS público do canal (sem chave) para títulos/descrições.
- stocktwits_symbol: stream público por ticker.

Instagram e TikTok não têm API pública de leitura: usar exportações manuais
ou ferramentas de terceiros, gravando no JSONL de posts.
"""
from __future__ import annotations

import html
import os
import re
from datetime import datetime, timezone

from .posts import Post

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

UA = "assessor-investimentos/0.1"


def _req():
    if requests is None:
        raise RuntimeError("instale `requests`")
    return requests


def reddit_public(subreddit: str, listing: str = "new", limit: int = 50) -> list[Post]:
    r = _req().get(f"https://www.reddit.com/r/{subreddit}/{listing}.json",
                   params={"limit": limit}, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    out = []
    for child in r.json().get("data", {}).get("children", []):
        d = child["data"]
        out.append(Post(author=d.get("author", ""), platform="reddit",
                        ts=datetime.fromtimestamp(d["created_utc"], tz=timezone.utc),
                        text=f"{d.get('title', '')}\n{d.get('selftext', '')}",
                        url="https://www.reddit.com" + d.get("permalink", ""),
                        engagement=int(d.get("score", 0)) + int(d.get("num_comments", 0))))
    return out


_TG_MSG = re.compile(r'data-post="([^"]+)".*?<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>.*?<time[^>]*datetime="([^"]+)"', re.S)
_TAG = re.compile(r"<[^>]+>")


def telegram_public_channel(channel: str) -> list[Post]:
    r = _req().get(f"https://t.me/s/{channel}", headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    out = []
    for post_id, body, dt in _TG_MSG.findall(r.text):
        text = html.unescape(_TAG.sub(" ", body.replace("<br/>", "\n")))
        out.append(Post(author=channel, platform="telegram", ts=datetime.fromisoformat(dt),
                        text=text.strip(), url=f"https://t.me/{post_id}"))
    return out


def x_recent_search(query: str, max_results: int = 50) -> list[Post]:
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        raise RuntimeError("defina X_BEARER_TOKEN (API v2 do X)")
    r = _req().get("https://api.x.com/2/tweets/search/recent",
                   params={"query": query, "max_results": min(100, max_results),
                           "tweet.fields": "created_at,public_metrics,author_id", "expansions": "author_id",
                           "user.fields": "username"},
                   headers={"Authorization": f"Bearer {token}", "User-Agent": UA}, timeout=20)
    r.raise_for_status()
    data = r.json()
    users = {u["id"]: u["username"] for u in data.get("includes", {}).get("users", [])}
    out = []
    for t in data.get("data", []):
        m = t.get("public_metrics", {})
        out.append(Post(author=users.get(t["author_id"], t["author_id"]), platform="x",
                        ts=datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")),
                        text=t["text"], url=f"https://x.com/i/status/{t['id']}",
                        engagement=sum(m.get(k, 0) for k in ("like_count", "retweet_count", "reply_count", "quote_count"))))
    return out


def youtube_channel_uploads(channel_id: str) -> list[Post]:
    from ..data.market import parse_rss
    r = _req().get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
                   headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    out = []
    for it in parse_rss(r.text, limit=30):
        ts = datetime.fromisoformat(it["published"]) if it["published"] else datetime.now(timezone.utc)
        out.append(Post(author=channel_id, platform="youtube", ts=ts,
                        text=f"{it['title']}\n{it['summary']}", url=it["link"]))
    return out


def stocktwits_symbol(symbol: str) -> list[Post]:
    r = _req().get(f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json",
                   headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    out = []
    for m in r.json().get("messages", []):
        sent = (m.get("entities", {}).get("sentiment") or {}).get("basic", "")
        stance = {"Bullish": "compra", "Bearish": "venda"}.get(sent, "")
        out.append(Post(author=m["user"]["username"], platform="stocktwits",
                        ts=datetime.fromisoformat(m["created_at"].replace("Z", "+00:00")),
                        text=m["body"], engagement=int((m.get("likes") or {}).get("total", 0)),
                        stance=stance))
    return out
