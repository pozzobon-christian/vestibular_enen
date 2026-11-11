"""Tendência por cálculo, não por olho.

- slope_tstat: regressão linear do log-preço nos últimos n dias; o t-stat da
  inclinação diz se a tendência é estatisticamente distinguível de ruído.
- adx: força de tendência (Wilder). > 25 tendência; < 20 lateral.
- momentum_rank: retorno 12-1 (12 meses excluindo o último) e 3 meses.
- breakout: fechamento acima da máxima de n dias (ou abaixo da mínima).
- vol_regime: vol realizada 20d vs 100d (expansão/compressão).
- trend_score: combinação transparente em 0-100 com direção.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


def slope_tstat(closes: Sequence[float], n: int = 60) -> tuple[float, float]:
    """(inclinação anualizada em %, t-stat) da regressão de ln(preço) ~ tempo."""
    ys = [math.log(c) for c in closes[-n:] if c > 0]
    m = len(ys)
    if m < 10:
        return 0.0, 0.0
    xs = list(range(m))
    xm, ym = sum(xs) / m, sum(ys) / m
    sxx = sum((x - xm) ** 2 for x in xs)
    sxy = sum((x - xm) * (y - ym) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = ym - b * xm
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    s2 = sum(r * r for r in resid) / (m - 2)
    se = math.sqrt(s2 / sxx) if sxx > 0 and s2 > 0 else 1e-9
    return (math.exp(b * 252) - 1) * 100, b / se


def adx(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], n: int = 14) -> float | None:
    if len(closes) < 2 * n + 1:
        return None
    tr, pdm, mdm = [], [], []
    for i in range(1, len(closes)):
        up, dn = highs[i] - highs[i - 1], lows[i - 1] - lows[i]
        pdm.append(up if up > dn and up > 0 else 0.0)
        mdm.append(dn if dn > up and dn > 0 else 0.0)
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    def wilder(xs):
        s = sum(xs[:n]); out = [s]
        for x in xs[n:]:
            s = s - s / n + x; out.append(s)
        return out
    trs, pds, mds = wilder(tr), wilder(pdm), wilder(mdm)
    dx = []
    for t, p, m in zip(trs, pds, mds):
        if t == 0:
            dx.append(0.0); continue
        pdi, mdi = 100 * p / t, 100 * m / t
        dx.append(100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0.0)
    a = sum(dx[:n]) / n
    for x in dx[n:]:
        a = (a * (n - 1) + x) / n
    return a


def momentum(closes: Sequence[float]) -> dict[str, float | None]:
    def ret(k_from: int, k_to: int = 0) -> float | None:
        if len(closes) <= k_from:
            return None
        base = closes[-1 - k_from]
        end = closes[-1 - k_to]
        return end / base - 1 if base else None
    return {"m_12_1": ret(252, 21), "m_3": ret(63), "m_1": ret(21), "m_1w": ret(5)}


def breakout(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], n: int = 20) -> str:
    if len(closes) < n + 1:
        return "nenhum"
    if closes[-1] > max(highs[-n - 1:-1]):
        return f"rompimento_alta_{n}d"
    if closes[-1] < min(lows[-n - 1:-1]):
        return f"rompimento_baixa_{n}d"
    return "nenhum"


def vol_regime(closes: Sequence[float]) -> dict[str, float | None]:
    rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes)) if closes[i - 1]]
    def sd(xs):
        if len(xs) < 2:
            return None
        m = sum(xs) / len(xs)
        return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) * math.sqrt(252)
    v20, v100 = sd(rets[-20:]), sd(rets[-100:])
    return {"vol_20d": v20, "vol_100d": v100, "razao": (v20 / v100) if v20 and v100 else None}


@dataclass(frozen=True)
class TrendReport:
    ticker: str
    direction: str          # alta | baixa | lateral
    score: int              # 0..100 força da evidência
    slope_annual_pct: float
    tstat: float
    adx: float | None
    above_sma50: bool
    above_sma200: bool | None
    breakout: str
    momentum: dict
    vol: dict
    notes: list[str]


def trend_report(ticker: str, highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]) -> TrendReport:
    notes: list[str] = []
    slope, t = slope_tstat(closes, 60)
    a = adx(highs, lows, closes)
    sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else closes[-1]
    sma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
    above50 = closes[-1] > sma50
    above200 = closes[-1] > sma200 if sma200 else None
    bo = breakout(highs, lows, closes)
    mom = momentum(closes)
    vol = vol_regime(closes)
    score = 0
    if abs(t) >= 2.0: score += 25; notes.append(f"inclinação 60d significativa (t={t:.1f})")
    elif abs(t) >= 1.0: score += 10
    if a is not None and a >= 25: score += 20; notes.append(f"ADX {a:.0f}: tendência com força")
    elif a is not None and a < 20: notes.append(f"ADX {a:.0f}: lateral")
    if above50 == (slope > 0): score += 15
    if above200 is not None and above200 == (slope > 0): score += 15
    if bo != "nenhum": score += 15; notes.append(bo)
    if mom["m_3"] is not None and (mom["m_3"] > 0) == (slope > 0): score += 10
    if vol["razao"] and vol["razao"] > 1.5: notes.append("vol em expansão: reduzir tamanho")
    direction = "alta" if slope > 0 and t >= 1.0 else "baixa" if slope < 0 and t <= -1.0 else "lateral"
    return TrendReport(ticker, direction, min(100, score), round(slope, 1), round(t, 2),
                       round(a, 1) if a is not None else None, above50, above200, bo,
                       {k: (round(v, 4) if v is not None else None) for k, v in mom.items()},
                       {k: (round(v, 4) if v is not None else None) for k, v in vol.items()}, notes)
