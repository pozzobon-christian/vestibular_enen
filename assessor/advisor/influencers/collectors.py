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


_reddit_token: dict = {}


def _reddit_headers() -> tuple[str, dict]:
    """Com REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET usa OAuth (funciona em IPs de
    nuvem, que o endpoint público bloqueia). Sem eles, tenta o público."""
    cid, sec = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
    ua = os.environ.get("REDDIT_USER_AGENT", "script:assessor-investimentos:0.1 (monitor)")
    if not (cid and sec):
        return "https://www.reddit.com", {"User-Agent": ua}
    import time as _t
    if _reddit_token.get("exp", 0) < _t.time() + 60:
        r = _req().post("https://www.reddit.com/api/v1/access_token", auth=(cid, sec),
                        data={"grant_type": "client_credentials"}, headers={"User-Agent": ua}, timeout=20)
        r.raise_for_status()
        j = r.json()
        _reddit_token.update(token=j["access_token"], exp=_t.time() + int(j.get("expires_in", 3600)))
    return "https://oauth.reddit.com", {"User-Agent": ua, "Authorization": f"Bearer {_reddit_token['token']}"}


def reddit_public(subreddit: str, listing: str = "new", limit: int = 50) -> list[Post]:
    base, headers = _reddit_headers()
    path = f"/r/{subreddit}/{listing}" + ("" if "oauth" in base else ".json")
    r = _req().get(base + path, params={"limit": limit}, headers=headers, timeout=20)
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


_YT_CANON = re.compile(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]+)"')
_YT_EXTERNAL = re.compile(r'"externalId":"(UC[\w-]+)"')
_YT_ANY = re.compile(r'"channelId":"(UC[\w-]+)"')
_YT_SEARCH = re.compile(r'"channelRenderer":\{"channelId":"(UC[\w-]+)"')
_YT_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " + UA,
               "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8", "Cookie": "CONSENT=YES+1; SOCS=CAI"}
_YT_RSS_HEADERS = {"User-Agent": "Mozilla/5.0"}   # o feed responde 404 quando recebe o cookie de consentimento


def youtube_feed_ok(channel_id: str) -> bool:
    """Aceita o ID se o RSS responder OU se a página /videos do canal existir
    (o RSS falha de forma intermitente em IPs de nuvem)."""
    r = _req().get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
                   headers=_YT_RSS_HEADERS, timeout=20)
    if r.status_code == 200 and "<feed" in r.text:
        return True
    r = _req().get(f"https://www.youtube.com/channel/{channel_id}/videos", headers=_YT_HEADERS, timeout=20)
    return r.status_code == 200 and '"videoId"' in r.text


_YT_VIDEO_UNUSED = re.compile(
    r'"videoRenderer":\{"videoId":"([\w-]{11})".*?"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)*)"'
    r'.*?(?:"publishedTimeText":\{"simpleText":"([^"]*)")?.*?(?:"viewCountText":\{"simpleText":"([^"]*)")?', re.S)
_REL = [("segundo", 1), ("minuto", 60), ("hora", 3600), ("dia", 86400), ("semana", 604800),
        ("mês", 2592000), ("mes", 2592000), ("ano", 31536000),
        ("second", 1), ("minute", 60), ("hour", 3600), ("day", 86400), ("week", 604800), ("month", 2592000), ("year", 31536000)]


def _relative_to_dt(text: str) -> datetime:
    """'há 3 dias' / '3 days ago' -> datetime aproximado (UTC)."""
    now = datetime.now(timezone.utc)
    m = re.search(r"(\d+)", text or "")
    if not m:
        return now
    n = int(m.group(1))
    low = text.lower()
    for word, secs in _REL:
        if word in low:
            from datetime import timedelta
            return now - timedelta(seconds=n * secs)
    return now


def _parse_lockups(body: str, limit: int) -> list[tuple[str, str, str, str]]:
    """(videoId, titulo, texto_publicacao, texto_views) do layout lockupViewModel."""
    out = []
    for chunk in body.split('"lockupViewModel":{"contentId":"')[1:]:
        vid = chunk[:11]
        if not re.fullmatch(r"[\w-]{11}", vid) or '"contentType":"LOCKUP_CONTENT_TYPE_VIDEO"' not in chunk[:200]:
            continue
        title = (re.search(r'"lockupMetadataViewModel":\{"title":\{"content":"((?:[^"\\]|\\.)*)"', chunk)
                 or re.search(r'"title":\{"content":"((?:[^"\\]|\\.)*)"', chunk)
                 or re.search(r'"accessibilityText":"((?:[^"\\]|\\.)*)"', chunk))
        if not title:
            continue
        parts = re.findall(r'"text":\{"content":"([^"]*)"', chunk.split('"metadataParts"', 1)[-1][:1500])
        pub = next((t for t in parts if re.search(r"\bhá\b|ago|atrás", t)), "")
        views = next((t for t in parts if re.search(r"visualiza|views|mil|mi\b", t)), "")
        out.append((vid, title.group(1), pub, views))
        if len(out) >= limit:
            break
    return out


def _parse_video_renderers(body: str, limit: int) -> list[tuple[str, str, str, str]]:
    out = []
    for chunk in body.split('"videoRenderer":')[1:limit + 1]:
        vid = re.search(r'"videoId":"([\w-]{11})"', chunk)
        title = re.search(r'"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)*)"', chunk)
        pub = re.search(r'"publishedTimeText":\{"simpleText":"([^"]*)"', chunk)
        views = re.search(r'"viewCountText":\{"simpleText":"([^"]*)"', chunk)
        if vid and title:
            out.append((vid.group(1), title.group(1), pub.group(1) if pub else "", views.group(1) if views else ""))
    return out


def _views_to_int(text: str) -> int:
    m = re.search(r"([\d.,]+)\s*(mil|mi|k|m|b)?", text.lower())
    if not m:
        return 0
    num = float(m.group(1).replace(".", "").replace(",", ".")) if m.group(2) else float(re.sub(r"\D", "", m.group(1)) or 0)
    mult = {"mil": 1e3, "k": 1e3, "mi": 1e6, "m": 1e6, "b": 1e9}.get(m.group(2) or "", 1)
    return int(num * mult)


def youtube_channel_videos_page(channel_id: str, limit: int = 30) -> list[Post]:
    """Vídeos recentes lidos da página /videos (ytInitialData). Data aproximada
    a partir do texto relativo ("há 2 dias")."""
    r = _req().get(f"https://www.youtube.com/channel/{channel_id}/videos", headers=_YT_HEADERS, timeout=20)
    r.raise_for_status()
    items = _parse_lockups(r.text, limit) or _parse_video_renderers(r.text, limit)
    out = []
    for vid, title, pub, views in items:
        out.append(Post(author=channel_id, platform="youtube", ts=_relative_to_dt(pub),
                        text=title.encode().decode("unicode_escape", errors="ignore"),
                        url=f"https://www.youtube.com/watch?v={vid}", engagement=_views_to_int(views)))
    return out


def youtube_channel_uploads(channel_id: str) -> list[Post]:
    from ..data.market import parse_rss
    r = _req().get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
                   headers=_YT_RSS_HEADERS, timeout=20)
    if r.status_code != 200 or "<entry>" not in r.text:
        return youtube_channel_videos_page(channel_id)
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
