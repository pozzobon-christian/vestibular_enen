"""Indicadores técnicos básicos (listas de floats). Usados para timing e
stops, nunca como tese isolada."""
from __future__ import annotations

from typing import Sequence


def sma(xs: Sequence[float], n: int) -> list[float | None]:
    out: list[float | None] = []
    s = 0.0
    for i, x in enumerate(xs):
        s += x
        if i >= n:
            s -= xs[i - n]
        out.append(s / n if i >= n - 1 else None)
    return out


def ema(xs: Sequence[float], n: int) -> list[float | None]:
    out: list[float | None] = []
    k = 2 / (n + 1)
    prev: float | None = None
    for i, x in enumerate(xs):
        if i < n - 1:
            out.append(None)
            continue
        if prev is None:
            prev = sum(xs[:n]) / n
        else:
            prev = x * k + prev * (1 - k)
        out.append(prev)
    return out


def rsi(closes: Sequence[float], n: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0); losses += max(-d, 0)
    ag, al = gains / n, losses / n
    out[n] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], n: int = 14) -> list[float | None]:
    trs: list[float] = []
    for i in range(len(closes)):
        if i == 0:
            trs.append(highs[0] - lows[0])
        else:
            trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    return sma(trs, n)


def bollinger(closes: Sequence[float], n: int = 20, k: float = 2.0) -> list[tuple[float, float, float] | None]:
    out: list[tuple[float, float, float] | None] = []
    for i in range(len(closes)):
        if i < n - 1:
            out.append(None); continue
        window = closes[i - n + 1:i + 1]
        m = sum(window) / n
        sd = (sum((x - m) ** 2 for x in window) / n) ** 0.5
        out.append((m - k * sd, m, m + k * sd))
    return out
