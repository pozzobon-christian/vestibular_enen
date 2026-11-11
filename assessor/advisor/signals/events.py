"""Especulação com notícias, com evidência.

1. Estudo de evento: para cada ativo, mede o retorno médio em 1 e 5 dias após
   notícias de sentimento forte (positivo e negativo) no histórico coletado.
   Sem histórico suficiente (n < 8 eventos), o sinal de notícia NÃO opera.
2. Sinal do dia: notícias das últimas `hours` horas por ativo; agrega
   sentimento ponderado por fonte, conta o número de fontes independentes e
   cruza com a reação histórica. Sinal só com >= 2 fontes e |score| >= 0,25.
"""
from __future__ import annotations

import json
from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import mean

SOURCE_WEIGHT = {"oficial": 1.0, "imprensa": 0.7, "alternativa": 0.3}


@dataclass(frozen=True)
class EventStats:
    ticker: str
    n_pos: int
    n_neg: int
    ret1_after_pos: float | None
    ret5_after_pos: float | None
    ret1_after_neg: float | None
    ret5_after_neg: float | None

    def reliable(self) -> bool:
        return (self.n_pos + self.n_neg) >= 8


def _fwd(closes: list[tuple[date, float]], d0: date, k: int) -> float | None:
    days = [d for d, _ in closes]
    i = bisect_left(days, d0)
    if i >= len(closes) or i + k >= len(closes):
        return None
    return closes[i + k][1] / closes[i][1] - 1


def event_study(db, ticker: str, threshold: float = 0.25) -> EventStats:
    rows = db.conn.execute("SELECT published, sentiment FROM news WHERE tickers LIKE ? AND ABS(sentiment) >= ?",
                           (f'%"{ticker}"%', threshold)).fetchall()
    closes = db.closes(ticker)
    pos1, pos5, neg1, neg5 = [], [], [], []
    for pub, sent in rows:
        d0 = datetime.fromisoformat(pub).date()
        r1, r5 = _fwd(closes, d0, 1), _fwd(closes, d0, 5)
        if r1 is None:
            continue
        (pos1 if sent > 0 else neg1).append(r1)
        if r5 is not None:
            (pos5 if sent > 0 else neg5).append(r5)
    m = lambda xs: round(mean(xs), 4) if xs else None
    return EventStats(ticker, len(pos1), len(neg1), m(pos1), m(pos5), m(neg1), m(neg5))


@dataclass(frozen=True)
class NewsSignal:
    ticker: str
    score: float
    n_items: int
    n_sources: int
    headlines: list[str]
    evidence: EventStats
    action: str
    reasons: list[str]


def news_signals(db, hours: float = 14.0, min_sources: int = 2, min_score: float = 0.25) -> list[NewsSignal]:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = db.conn.execute("SELECT source, kind, title, tickers, sentiment, published FROM news WHERE published >= ?",
                           (since,)).fetchall()
    by: dict[str, list] = {}
    for src, kind, title, tickers, sent, pub in rows:
        for t in json.loads(tickers or "[]"):
            by.setdefault(t, []).append((src, kind, title, sent))
    out = []
    for t, items in by.items():
        w = [(SOURCE_WEIGHT.get(k, 0.5), s) for _, k, _, s in items]
        score = sum(a * b for a, b in w) / sum(a for a, _ in w)
        sources = {src for src, *_ in items}
        ev = event_study(db, t)
        reasons = []
        if len(sources) < min_sources:
            action = "ignorar"; reasons.append("uma única fonte")
        elif abs(score) < min_score:
            action = "ignorar"; reasons.append("sentimento fraco")
        elif not ev.reliable():
            action = "observar"; reasons.append(f"sem histórico de reação suficiente (n={ev.n_pos + ev.n_neg} eventos)")
        else:
            hist = ev.ret1_after_pos if score > 0 else ev.ret1_after_neg
            if hist is None:
                action = "observar"; reasons.append("sem retorno histórico medido")
            elif (score > 0 and hist > 0.003) or (score < 0 and hist < -0.003):
                action = "compra" if score > 0 else "venda"; reasons.append(f"reação histórica média 1d: {hist:+.2%}")
            elif (score > 0 and hist < -0.003) or (score < 0 and hist > 0.003):
                action = "contrarian"; reasons.append(f"mercado historicamente faz o oposto da notícia ({hist:+.2%})")
            else:
                action = "ignorar"; reasons.append("reação histórica próxima de zero")
        out.append(NewsSignal(t, round(score, 3), len(items), len(sources), [i[2] for i in items[:4]], ev, action, reasons))
    return sorted(out, key=lambda s: (-abs(s.score) * s.n_sources))
