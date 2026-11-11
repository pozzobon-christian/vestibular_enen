"""Casos do passado semelhantes ao momento atual (análogos).

Descreve o "estado" de um ativo por um vetor simples (retornos de 5/20/60
dias, distância da MM50 e MM200, RSI, vol 20d relativa, drawdown da máxima
de 120d) e procura, no histórico do próprio ativo e opcionalmente de outros,
as janelas mais parecidas. Devolve o que aconteceu DEPOIS delas: distribuição
dos retornos em 5, 10 e 20 dias. É evidência estatística, não garantia.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .technical import rsi


def state_vector(closes: Sequence[float], i: int) -> list[float] | None:
    if i < 200 or i >= len(closes):
        return None
    c = closes[i]
    r = lambda k: c / closes[i - k] - 1
    sma50 = sum(closes[i - 49:i + 1]) / 50
    sma200 = sum(closes[i - 199:i + 1]) / 200
    rets = [closes[j] / closes[j - 1] - 1 for j in range(i - 19, i + 1)]
    m = sum(rets) / 20
    v20 = math.sqrt(sum((x - m) ** 2 for x in rets) / 19)
    rets100 = [closes[j] / closes[j - 1] - 1 for j in range(i - 99, i + 1)]
    m2 = sum(rets100) / 100
    v100 = math.sqrt(sum((x - m2) ** 2 for x in rets100) / 99) or 1e-9
    dd = c / max(closes[i - 119:i + 1]) - 1
    rs = rsi(closes[i - 30:i + 1])[-1] or 50.0
    return [r(5), r(20), r(60), c / sma50 - 1, c / sma200 - 1, (rs - 50) / 50, v20 / v100 - 1, dd]


def _dist(a: list[float], b: list[float], w: list[float]) -> float:
    return math.sqrt(sum(wi * (x - y) ** 2 for x, y, wi in zip(a, b, w)))


@dataclass(frozen=True)
class AnalogResult:
    ticker: str
    n: int
    horizons: dict            # {5: {"media":..,"mediana":..,"p_positivo":..,"pior":..,"melhor":..}, 10:..., 20:...}
    examples: list[dict]      # [{"indice":..,"distancia":..,"ret_20d":..}]
    state: list[float]


def find_analogs(ticker: str, closes: Sequence[float], dates: Sequence[str] | None = None, k: int = 15,
                 min_gap: int = 20, extra: dict[str, Sequence[float]] | None = None) -> AnalogResult | None:
    """k janelas mais parecidas com hoje (excluindo os últimos 20 dias e janelas
    vizinhas entre si). `extra` permite buscar também em outros ativos."""
    n = len(closes)
    cur = state_vector(closes, n - 1)
    if cur is None:
        return None
    w = [1.0, 1.5, 1.0, 1.5, 1.0, 1.0, 0.7, 1.2]
    cands: list[tuple[float, str, int, Sequence[float]]] = []
    pools = {ticker: closes, **(extra or {})}
    for name, series in pools.items():
        last_ok = len(series) - 21 if name == ticker else len(series) - 21
        for i in range(200, last_ok):
            sv = state_vector(series, i)
            if sv is None:
                continue
            cands.append((_dist(cur, sv, w), name, i, series))
    cands.sort(key=lambda t: t[0])
    chosen: list[tuple[float, str, int, Sequence[float]]] = []
    for c in cands:
        if all(not (c[1] == x[1] and abs(c[2] - x[2]) < min_gap) for x in chosen):
            chosen.append(c)
        if len(chosen) >= k:
            break
    if not chosen:
        return None
    horizons = {}
    for h in (5, 10, 20):
        rets = [s[i + h] / s[i] - 1 for _, _, i, s in chosen if i + h < len(s)]
        if not rets:
            continue
        srt = sorted(rets)
        horizons[h] = {"media": round(sum(rets) / len(rets), 4), "mediana": round(srt[len(srt) // 2], 4),
                       "p_positivo": round(sum(1 for r in rets if r > 0) / len(rets), 2),
                       "pior": round(srt[0], 4), "melhor": round(srt[-1], 4), "n": len(rets)}
    examples = [{"ativo": name, "indice": i, "data": (dates[i] if dates and name == ticker and i < len(dates) else None),
                 "distancia": round(d, 3), "ret_20d": round(s[i + 20] / s[i] - 1, 4) if i + 20 < len(s) else None}
                for d, name, i, s in chosen[:8]]
    return AnalogResult(ticker, len(chosen), horizons, examples, [round(x, 4) for x in cur])
