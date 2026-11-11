"""Métricas de risco sobre séries de retornos (listas de floats, retornos simples)."""
from __future__ import annotations

import math
from typing import Sequence


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: Sequence[float], ddof: int = 1) -> float:
    n = len(xs)
    if n - ddof <= 0:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - ddof))


def annualized_volatility(returns: Sequence[float], periods_per_year: int = 252) -> float:
    return _std(returns) * math.sqrt(periods_per_year)


def sharpe_ratio(returns: Sequence[float], risk_free_per_period: float = 0.0,
                 periods_per_year: int = 252) -> float:
    excess = [r - risk_free_per_period for r in returns]
    sd = _std(excess)
    if sd == 0:
        return 0.0
    return _mean(excess) / sd * math.sqrt(periods_per_year)


def sortino_ratio(returns: Sequence[float], target: float = 0.0,
                  periods_per_year: int = 252) -> float:
    downside = [min(0.0, r - target) ** 2 for r in returns]
    dd = math.sqrt(_mean(downside)) if downside else 0.0
    if dd == 0:
        return 0.0
    return (_mean(returns) - target) / dd * math.sqrt(periods_per_year)


def max_drawdown(equity_curve: Sequence[float]) -> float:
    """Maior queda percentual do pico ao vale (valor positivo, ex.: 0.25 = 25%)."""
    peak = -math.inf
    mdd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, (peak - v) / peak)
    return mdd


def value_at_risk(returns: Sequence[float], confidence: float = 0.95) -> float:
    """VaR histórico: perda (positiva) não excedida com a confiança dada."""
    if not returns:
        return 0.0
    xs = sorted(returns)
    idx = int((1 - confidence) * len(xs))
    idx = min(max(idx, 0), len(xs) - 1)
    return -xs[idx]


def expected_shortfall(returns: Sequence[float], confidence: float = 0.95) -> float:
    """CVaR: perda média nos piores (1-confiança) cenários."""
    if not returns:
        return 0.0
    xs = sorted(returns)
    k = max(1, int((1 - confidence) * len(xs)))
    tail = xs[:k]
    return -_mean(tail)
