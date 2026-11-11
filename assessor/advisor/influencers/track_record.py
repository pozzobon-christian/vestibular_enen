"""Histórico de acerto: cada chamada (post com ativo + direção) é comparada com o
retorno do ativo nos dias seguintes. Separa quem move o mercado de quem só
faz barulho, e identifica a assinatura de pump-and-dump (sobe rápido, devolve
tudo em semanas).
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, datetime
from statistics import mean

from .posts import Post


@dataclass(frozen=True)
class CallOutcome:
    author: str
    ticker: str
    stance: str
    ts: datetime
    ret_1d: float | None
    ret_5d: float | None
    ret_20d: float | None

    def hit(self, horizon: str = "ret_5d") -> bool | None:
        r = getattr(self, horizon)
        if r is None:
            return None
        return r > 0 if self.stance == "compra" else r < 0


def _forward_return(closes: list[tuple[date, float]], d0: date, days: int) -> float | None:
    dates = [d for d, _ in closes]
    i = bisect_left(dates, d0)
    if i >= len(closes) or i + days >= len(closes):
        return None
    base = closes[i][1]
    return closes[i + days][1] / base - 1 if base else None


def evaluate_calls(posts: list[Post], prices: dict[str, list[tuple[date, float]]]) -> list[CallOutcome]:
    """prices: ticker -> lista ordenada de (data, fechamento)."""
    out: list[CallOutcome] = []
    for p in posts:
        if p.stance == "neutro":
            continue
        for t in p.tickers:
            series = prices.get(t)
            if not series:
                continue
            d0 = p.ts.date()
            out.append(CallOutcome(p.author_key, t, p.stance, p.ts,
                                   _forward_return(series, d0, 1),
                                   _forward_return(series, d0, 5),
                                   _forward_return(series, d0, 20)))
    return out


def influencer_stats(outcomes: list[CallOutcome]) -> dict[str, dict]:
    by: dict[str, list[CallOutcome]] = {}
    for o in outcomes:
        by.setdefault(o.author, []).append(o)
    stats: dict[str, dict] = {}
    for a, lst in by.items():
        def _hr(h: str) -> float | None:
            hs = [o.hit(h) for o in lst if o.hit(h) is not None]
            return round(sum(hs) / len(hs), 3) if hs else None
        def _avg(h: str) -> float | None:
            rs = [getattr(o, h) * (1 if o.stance == "compra" else -1) for o in lst if getattr(o, h) is not None]
            return round(mean(rs), 4) if rs else None
        stats[a] = {
            "chamadas": len(lst),
            "acerto_1d": _hr("ret_1d"), "acerto_5d": _hr("ret_5d"), "acerto_20d": _hr("ret_20d"),
            "retorno_medio_1d": _avg("ret_1d"), "retorno_medio_5d": _avg("ret_5d"), "retorno_medio_20d": _avg("ret_20d"),
            "assinatura_pump": pump_signature(lst),
        }
    return stats


def pump_signature(outcomes: list[CallOutcome]) -> float:
    """Fração das chamadas de compra em que o ativo subiu em 1 dia e estava
    abaixo do preço da chamada em 20 dias. > 0,5 = padrão de pump-and-dump:
    quem segue esse autor é liquidez de saída."""
    buys = [o for o in outcomes if o.stance == "compra" and o.ret_1d is not None and o.ret_20d is not None]
    if not buys:
        return 0.0
    pumps = sum(1 for o in buys if o.ret_1d > 0 and o.ret_20d < 0)
    return round(pumps / len(buys), 3)
