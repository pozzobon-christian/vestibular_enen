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


def fetch_daily_bars(ticker: str, market: str = "BR", timeout: int = 20) -> list[PriceBar]:
    _require_requests()
    url = f"https://stooq.com/q/d/l/?s={stooq_symbol(ticker, market)}&i=d"
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return parse_stooq_csv(resp.text)


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
