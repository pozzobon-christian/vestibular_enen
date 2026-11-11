"""Conectores de dados de mercado. Dependem apenas de `requests` e usam
APIs públicas; todos retornam estruturas simples e falham com exceção clara.

- fetch_daily_bars: Stooq (CSV público) para ações BR/US e índices.
- fetch_crypto_price: CoinGecko (sem chave, limitado).
- fetch_rss: feeds RSS (RI, reguladores, notícias).

Corretoras (execução) ficam em portfolio/broker.py com interface abstrata:
a conta real é conectada pelo usuário com as próprias chaves.
"""
from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

USER_AGENT = "assessor-investimentos/0.1"


@dataclass(frozen=True)
class PriceBar:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float


def _require_requests():
    if requests is None:
        raise RuntimeError("instale `requests` para usar os conectores")


def stooq_symbol(ticker: str, market: str) -> str:
    """PETR4 (BR) -> petr4.br ; AAPL (US) -> aapl.us"""
    suffix = {"BR": ".br", "US": ".us"}.get(market.upper(), "")
    return ticker.lower() + suffix


def yahoo_symbol(ticker: str, market: str) -> str:
    """PETR4 (BR) -> PETR4.SA ; AAPL (US) -> AAPL"""
    return f"{ticker}.SA" if market.upper() == "BR" else ticker


def fetch_daily_bars_yahoo(ticker: str, market: str = "BR", range_: str = "2y", timeout: int = 20) -> list[PriceBar]:
    _require_requests()
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol(ticker, market)}"
    resp = requests.get(url, params={"range": range_, "interval": "1d"}, timeout=timeout,
                        headers={"User-Agent": "Mozilla/5.0 " + USER_AGENT})
    resp.raise_for_status()
    return parse_yahoo_chart(resp.json())


def parse_yahoo_chart(data: dict) -> list[PriceBar]:
    from datetime import datetime, timezone
    result = (data.get("chart") or {}).get("result") or []
    if not result:
        raise ValueError("resposta Yahoo sem resultado")
    r = result[0]
    ts = r.get("timestamp") or []
    q = (r.get("indicators") or {}).get("quote", [{}])[0]
    bars = []
    for i, t in enumerate(ts):
        c = (q.get("close") or [None])[i]
        if c is None:
            continue
        bars.append(PriceBar(
            day=datetime.fromtimestamp(t, tz=timezone.utc).date(),
            open=float((q.get("open") or [c])[i] or c), high=float((q.get("high") or [c])[i] or c),
            low=float((q.get("low") or [c])[i] or c), close=float(c),
            volume=float((q.get("volume") or [0])[i] or 0)))
    return bars


def fetch_daily_bars(ticker: str, market: str = "BR", timeout: int = 20) -> list[PriceBar]:
    """Yahoo primeiro (aceita IPs de nuvem); Stooq como reserva."""
    _require_requests()
    try:
        bars = fetch_daily_bars_yahoo(ticker, market, timeout=timeout)
        if bars:
            return bars
    except Exception:  # noqa: BLE001
        pass
    url = f"https://stooq.com/q/d/l/?s={stooq_symbol(ticker, market)}&i=d"
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    bars = parse_stooq_csv(resp.text)
    if not bars:
        raise ValueError(f"sem dados para {ticker} ({resp.text[:80]!r})")
    return bars


def fetch_crypto_daily(coin_id: str, days: int = 365, vs: str = "usd", timeout: int = 20) -> list[PriceBar]:
    """Histórico diário via CoinGecko market_chart (sem chave)."""
    from datetime import datetime, timezone
    _require_requests()
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    resp = requests.get(url, params={"vs_currency": vs, "days": days, "interval": "daily"},
                        timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    prices = resp.json().get("prices", [])
    vols = {int(t // 86400000): v for t, v in resp.json().get("total_volumes", [])}
    bars = []
    for t, price in prices:
        d = datetime.fromtimestamp(t / 1000, tz=timezone.utc).date()
        if bars and bars[-1].day == d:
            continue
        bars.append(PriceBar(d, price, price, price, price, vols.get(int(t // 86400000), 0.0)))
    return bars


def parse_stooq_csv(text: str) -> list[PriceBar]:
    bars: list[PriceBar] = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            bars.append(PriceBar(
                day=date.fromisoformat(row["Date"]),
                open=float(row["Open"]), high=float(row["High"]),
                low=float(row["Low"]), close=float(row["Close"]),
                volume=float(row.get("Volume") or 0),
            ))
        except (KeyError, ValueError):
            continue
    return bars


def fetch_crypto_price(ids: list[str], vs: str = "usd", timeout: int = 20) -> dict[str, float]:
    _require_requests()
    url = "https://api.coingecko.com/api/v3/simple/price"
    resp = requests.get(url, params={"ids": ",".join(ids), "vs_currencies": vs},
                        timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    data = resp.json()
    return {k: float(v[vs]) for k, v in data.items() if vs in v}


def fetch_rss(url: str, timeout: int = 20, limit: int = 50) -> list[dict[str, str]]:
    _require_requests()
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return parse_rss(resp.text, limit)


def parse_rss(xml_text: str, limit: int = 50) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    items = []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for item in root.iter("item"):
        items.append({
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "published": (item.findtext("pubDate") or "").strip(),
            "summary": (item.findtext("description") or "").strip(),
        })
    for entry in root.findall(".//atom:entry", ns):
        link = entry.find("atom:link", ns)
        items.append({
            "title": (entry.findtext("atom:title", default="", namespaces=ns) or "").strip(),
            "link": link.get("href", "") if link is not None else "",
            "published": (entry.findtext("atom:updated", default="", namespaces=ns) or "").strip(),
            "summary": (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip(),
        })
    return items[:limit]
