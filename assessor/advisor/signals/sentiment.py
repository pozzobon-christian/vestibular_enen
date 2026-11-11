"""Sentimento por léxico (PT/EN) com ponderação por fonte e decaimento no tempo.

Não é um modelo de linguagem; é um termômetro rápido e barato para filtrar o
que merece leitura humana (ou de um LLM) e para detectar picos anormais de
menções. Para análise profunda, enviar os itens filtrados a um LLM.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone

POSITIVE = {
    # PT
    "alta", "sobe", "subiu", "lucro", "recorde", "crescimento", "supera", "superou", "forte",
    "aprovado", "dividendo", "dividendos", "recompra", "guidance", "otimista", "compra", "comprar",
    "oportunidade", "expansão", "recuperação", "valorização",
    # EN
    "beat", "beats", "record", "growth", "upgrade", "bullish", "buyback", "surge", "rally",
    "profit", "outperform", "strong", "approval", "partnership", "breakout",
}
NEGATIVE = {
    # PT
    "queda", "cai", "caiu", "prejuízo", "fraude", "investigação", "rebaixa", "rebaixado",
    "pessimista", "venda", "vender", "calote", "recuperação judicial", "greve", "multa",
    "demissão", "demissões", "desaba", "despenca", "risco", "vazamento", "hack",
    # EN
    "miss", "misses", "downgrade", "bearish", "lawsuit", "fraud", "probe", "bankruptcy",
    "default", "plunge", "crash", "layoffs", "fine", "halt", "delist", "exploit", "rug",
}
INTENSIFIERS = {"muito", "fortemente", "very", "massive", "huge", "enorme"}
NEGATIONS = {"não", "nao", "sem", "not", "no", "never", "nunca"}

SOURCE_WEIGHT = {
    "oficial": 1.0, "ri": 1.0, "regulador": 1.0, "imprensa": 0.7,
    "analista": 0.6, "x": 0.35, "reddit": 0.3, "telegram": 0.25, "discord": 0.25, "desconhecida": 0.2,
}

_token = re.compile(r"[a-záéíóúâêôãõç]+", re.IGNORECASE)


def score_text(text: str) -> float:
    """Retorna score em [-1, 1]."""
    words = [w.lower() for w in _token.findall(text)]
    if not words:
        return 0.0
    score = 0.0
    hits = 0
    for i, w in enumerate(words):
        s = 1.0 if w in POSITIVE else -1.0 if w in NEGATIVE else 0.0
        if s == 0.0:
            continue
        window = words[max(0, i - 2):i]
        if any(n in NEGATIONS for n in window):
            s = -s
        if any(n in INTENSIFIERS for n in window):
            s *= 1.5
        score += s
        hits += 1
    if hits == 0:
        return 0.0
    return max(-1.0, min(1.0, score / math.sqrt(len(words))))


@dataclass(frozen=True)
class SentimentItem:
    text: str
    source: str                  # chave de SOURCE_WEIGHT
    published: datetime
    ticker: str | None = None


def aggregate_sentiment(items: list[SentimentItem], now: datetime | None = None,
                        half_life_hours: float = 12.0) -> dict:
    """Média ponderada por confiabilidade da fonte e decaimento exponencial.
    Também devolve contagem por hora para detectar picos de menções."""
    now = now or datetime.now(timezone.utc)
    num = den = 0.0
    per_hour: dict[str, int] = {}
    for it in items:
        age_h = max(0.0, (now - it.published).total_seconds() / 3600)
        decay = 0.5 ** (age_h / half_life_hours)
        w = SOURCE_WEIGHT.get(it.source, SOURCE_WEIGHT["desconhecida"]) * decay
        num += w * score_text(it.text)
        den += w
        key = it.published.strftime("%Y-%m-%dT%H")
        per_hour[key] = per_hour.get(key, 0) + 1
    score = num / den if den else 0.0
    counts = list(per_hour.values())
    mean = sum(counts) / len(counts) if counts else 0.0
    spike = (max(counts) / mean) if mean else 0.0
    return {
        "score": round(score, 4),
        "n": len(items),
        "mentions_per_hour": per_hour,
        "spike_ratio": round(spike, 2),   # > 3 = pico anormal, olhar manualmente
        "label": "positivo" if score > 0.15 else "negativo" if score < -0.15 else "neutro",
    }
