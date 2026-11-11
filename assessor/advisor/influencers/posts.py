"""Posts públicos: extração de ativos mencionados e direção (compra/venda)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# PETR4, VALE3, BBAS3, ITSA4, BOVA11, HGLG11 (FIIs/ETFs terminam em 11), units 3/4/5/6/11
_BR = re.compile(r"\b([A-Z]{4}(?:3|4|5|6|11|31|32|33|34|35|39))\b")
# $AAPL, $TSLA, $BTC, $SOL
_CASHTAG = re.compile(r"\$([A-Z]{1,6})\b")
# nomes comuns de cripto sem cashtag
_CRYPTO_WORDS = {
    "bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH", "eth": "ETH", "solana": "SOL", "sol": "SOL",
    "xrp": "XRP", "ripple": "XRP", "doge": "DOGE", "dogecoin": "DOGE", "bnb": "BNB", "ada": "ADA",
    "cardano": "ADA", "avax": "AVAX", "link": "LINK", "chainlink": "LINK", "pepe": "PEPE", "shib": "SHIB",
}
_word = re.compile(r"[a-záéíóúâêôãõç$]+", re.IGNORECASE)

BUY_WORDS = {
    "compra", "comprei", "comprando", "compre", "comprar", "entrei", "entrando", "entrada", "aporte",
    "aportei", "oportunidade", "barata", "barato", "descontada", "vai subir", "alvo", "rompimento",
    "buy", "bought", "buying", "long", "accumulate", "accumulating", "moon", "bullish", "breakout",
    "calls", "undervalued", "dip", "load", "loading", "ape", "aping", "send", "lfg", "100x", "10x",
    "foguete", "🚀", "💎", "🙌", "🐂", "📈",
}
SELL_WORDS = {
    "venda", "vendi", "vendendo", "venda", "vender", "saí", "saindo", "zerei", "zerando", "realizei",
    "realizar", "cara", "esticada", "topo", "cuidado", "fuja", "fujam", "stop",
    "sell", "sold", "selling", "short", "shorting", "dump", "dumping", "overvalued", "bearish",
    "puts", "exit", "exited", "take profit", "top", "🐻", "📉", "🔻",
}
NEGATIONS = {"não", "nao", "nunca", "not", "no", "never", "don't", "dont"}


@dataclass
class Post:
    author: str                 # chave do registro: "x:@handle" ou só handle
    platform: str
    ts: datetime
    text: str
    url: str = ""
    engagement: int = 0         # likes + reposts + comentários (quanto alcançou)
    tickers: list[str] = field(default_factory=list)
    stance: str = ""            # compra | venda | neutro

    def __post_init__(self) -> None:
        if not self.tickers:
            self.tickers = extract_tickers(self.text)
        if not self.stance:
            self.stance = detect_stance(self.text)

    @property
    def author_key(self) -> str:
        h = self.author.split(":", 1)[-1].lstrip("@").lower()
        return f"{self.platform}:{h}"


def extract_tickers(text: str) -> list[str]:
    found: list[str] = []
    for m in _BR.findall(text):
        found.append(m)
    for m in _CASHTAG.findall(text):
        found.append(m)
    low = text.lower()
    for w in _word.findall(low):
        if w in _CRYPTO_WORDS:
            found.append(_CRYPTO_WORDS[w])
    seen: set[str] = set()
    out = []
    for t in found:
        if t not in seen:
            seen.add(t); out.append(t)
    return out


def detect_stance(text: str) -> str:
    low = text.lower()
    tokens = _word.findall(low)
    buy = sell = 0.0
    for i, w in enumerate(tokens):
        neg = any(n in NEGATIONS for n in tokens[max(0, i - 4):i])
        if w in BUY_WORDS:
            if neg: sell += 1
            else: buy += 1
        elif w in SELL_WORDS:
            if neg: buy += 1
            else: sell += 1
    for emo in BUY_WORDS:
        if len(emo) <= 2 and emo in text:
            buy += 1
    for emo in SELL_WORDS:
        if len(emo) <= 2 and emo in text:
            sell += 1
    if buy == sell:
        return "neutro"
    return "compra" if buy > sell else "venda"


def parse_posts_jsonl(path: Path | str) -> list[Post]:
    out: list[Post] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        row["ts"] = datetime.fromisoformat(row["ts"])
        out.append(Post(**row))
    return out
