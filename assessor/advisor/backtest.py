"""Backtest walk-forward do motor reduzido (tendência + análogos + regime +
porteiro + stop estrutural + alvo 2x risco), só com dados conhecidos em cada dia.

Limites honestos: sem notícias, balanços e intradia no passado (viram neutro);
lista de ativos escolhida hoje (viés de sobrevivência); custos de 0,05% por
lado; execução no fechamento do dia do sinal.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from .signals.analogs import state_vector, _dist
from .signals.gate import order_gate, stabilization, structural_stop
from .signals.technical import atr
from .signals.trend import trend_report, market_regime


@dataclass
class Trade:
    ticker: str
    entry_day: str
    entry: float
    stop: float
    target: float
    qty: int
    exit_day: str = ""
    exit: float = 0.0
    reason: str = ""
    pnl: float = 0.0


@dataclass
class Result:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[str, float]] = field(default_factory=list)
    signals_blocked: int = 0
    signals_total: int = 0


def _series(db, t):
    rows = db.conn.execute("SELECT day, high, low, close FROM prices WHERE ticker=? ORDER BY day", (t,)).fetchall()
    return [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows]


def _analog_vote(vecs: dict, t: str, i: int, pool: list[str], closes: dict, k: int = 15, min_gap: int = 20):
    cur = vecs[t][i]
    if cur is None:
        return "neutro", 0
    w = [1.0, 1.5, 1.0, 1.5, 1.0, 1.0, 0.7, 1.2]
    cands = []
    for name in pool:
        for j, v in enumerate(vecs[name]):
            if v is None or j > i - 21:
                continue
            cands.append((_dist(cur, v, w), name, j))
    cands.sort(key=lambda x: x[0])
    chosen = []
    for c in cands:
        if all(not (c[1] == x[1] and abs(c[2] - x[2]) < min_gap) for x in chosen):
            chosen.append(c)
        if len(chosen) >= k:
            break
    rets = [closes[n][j + 20] / closes[n][j] - 1 for _, n, j in chosen if j + 20 < len(closes[n])]
    if len(rets) < 8:
        return "neutro", len(rets)
    srt = sorted(rets); med = srt[len(srt) // 2]; pos = sum(1 for r in rets if r > 0) / len(rets)
    if pos >= 0.65 and med > 0.01:
        return "a_favor", len(rets)
    if pos <= 0.35 and med < -0.01:
        return "contra", len(rets)
    return "neutro", len(rets)


def run(db, tickers: list[str], index: str = "BOVA11", capital: float = 500.0, risk_pct: float = 0.02,
        max_pos: int = 2, hold_days: int = 5, start_offset: int = 230, cost: float = 0.0005, vix_ticker: str = "^VIX") -> Result:
    data = {t: _series(db, t) for t in tickers + [index]}
    data = {t: v for t, v in data.items() if len(v[0]) >= start_offset + 30}
    tickers = [t for t in tickers if t in data]
    closes = {t: data[t][3] for t in data}
    vecs = {t: [state_vector(closes[t], i) for i in range(len(closes[t]))] for t in data}
    vix_days, _, _, vix_close = _series(db, vix_ticker)
    vix_by_day = dict(zip(vix_days, vix_close))
    idx_days = data[index][0]
    res = Result()
    cash = capital
    open_trades: list[Trade] = []
    day_index = {t: {d: i for i, d in enumerate(data[t][0])} for t in data}
    for di, day in enumerate(idx_days):
        if di < start_offset:
            continue
        # marcar e fechar posições abertas
        for tr in list(open_trades):
            t = tr.ticker; i = day_index[t].get(day)
            if i is None:
                continue
            _, hi, lo, cl = data[t]
            held = i - day_index[t][tr.entry_day]
            exit_px = None; why = ""
            if lo[i] <= tr.stop:
                exit_px, why = tr.stop, "stop"
            elif hi[i] >= tr.target:
                exit_px, why = tr.target, "alvo"
            elif held >= hold_days:
                exit_px, why = cl[i], "tempo"
            if exit_px is not None:
                tr.exit_day, tr.exit, tr.reason = day, exit_px, why
                tr.pnl = (exit_px - tr.entry) * tr.qty - (tr.entry + exit_px) * tr.qty * cost
                cash += tr.pnl
                open_trades.remove(tr); res.trades.append(tr)
        # regime e VIX do dia
        reg = market_regime(closes[index][:di + 1], vix_by_day.get(day))
        vix = vix_by_day.get(day)
        # novos sinais
        if len(open_trades) < max_pos:
            cands = []
            for t in tickers:
                i = day_index[t].get(day)
                if i is None or i < 200 or any(x.ticker == t for x in open_trades):
                    continue
                _, hi, lo, cl = data[t]
                tr_ = trend_report(t, hi[:i + 1], lo[:i + 1], cl[:i + 1])
                av, n = _analog_vote(vecs, t, i, [x for x in tickers], closes)
                votes = {"tendencia": "a_favor" if tr_.direction == "alta" and tr_.score >= 50 else "contra" if tr_.direction == "baixa" and tr_.score >= 50 else "neutro",
                         "analogos": av, "balanco": None, "noticias": None, "intradia": None}
                res.signals_total += 1
                fav = sum(1 for v in votes.values() if v == "a_favor"); con = sum(1 for v in votes.values() if v == "contra")
                if not (fav >= 2 and con == 0):
                    continue
                stab = stabilization(hi[:i + 1], lo[:i + 1], cl[:i + 1], "compra")
                g = order_gate("buy", votes, tr_.direction, tr_.score, reg["modo"], stab, n, None, None, None, vix=vix)
                if not g.approved:
                    res.signals_blocked += 1; continue
                a = atr(hi[:i + 1], lo[:i + 1], cl[:i + 1])[-1] or 0.0
                stop = structural_stop(lo[:i + 1], hi[:i + 1], cl[:i + 1], a, "compra")
                risk_unit = cl[i] - stop
                if risk_unit <= 0:
                    continue
                qty = int((capital * risk_pct) / risk_unit)
                qty = min(qty, int(capital * 0.25 / cl[i]))
                if qty < 1:
                    continue
                cands.append((tr_.score, Trade(t, day, cl[i], round(stop, 4), round(cl[i] + 2 * risk_unit, 4), qty)))
            cands.sort(key=lambda x: -x[0])
            for _, tr in cands[:max_pos - len(open_trades)]:
                cash -= tr.entry * tr.qty * cost
                open_trades.append(tr)
        mark = sum((closes[tr.ticker][day_index[tr.ticker][day]] - tr.entry) * tr.qty for tr in open_trades if day in day_index[tr.ticker])
        res.equity_curve.append((day, round(cash + mark, 2)))
    return res


def summarize(res: Result, capital: float, index_closes: list[tuple[str, float]]) -> dict:
    eq = [v for _, v in res.equity_curve]
    if not eq:
        return {"erro": "sem curva"}
    peak = eq[0]; mdd = 0.0
    for v in eq:
        peak = max(peak, v); mdd = max(mdd, (peak - v) / peak)
    wins = [t for t in res.trades if t.pnl > 0]; losses = [t for t in res.trades if t.pnl <= 0]
    days = {d for d, _ in res.equity_curve}
    idx = [c for d, c in index_closes if d in days]
    weeks = len(eq) / 5
    return {
        "periodo": f"{res.equity_curve[0][0]} a {res.equity_curve[-1][0]} ({len(eq)} pregões, {weeks:.0f} semanas)",
        "capital_inicial": capital, "capital_final": eq[-1], "retorno_total": round(eq[-1] / capital - 1, 4),
        "retorno_semanal_medio": round((eq[-1] / capital) ** (1 / max(weeks, 1)) - 1, 4),
        "drawdown_maximo": round(mdd, 4), "operacoes": len(res.trades), "acerto": round(len(wins) / len(res.trades), 3) if res.trades else None,
        "ganho_medio": round(sum(t.pnl for t in wins) / len(wins), 2) if wins else 0, "perda_media": round(sum(t.pnl for t in losses) / len(losses), 2) if losses else 0,
        "saidas": {k: sum(1 for t in res.trades if t.reason == k) for k in ("alvo", "stop", "tempo")},
        "sinais_avaliados": res.signals_total, "bloqueados_pelo_porteiro": res.signals_blocked,
        "buy_and_hold_indice": round(idx[-1] / idx[0] - 1, 4) if len(idx) > 1 else None,
        "melhor_operacao": max(res.trades, key=lambda t: t.pnl).__dict__ if res.trades else None,
        "pior_operacao": min(res.trades, key=lambda t: t.pnl).__dict__ if res.trades else None,
    }


if __name__ == "__main__":
    import sys
    from .storage import MonitorDB
    db = MonitorDB("data/monitor.db")
    wl = json.load(open("data/watchlist.json", encoding="utf-8"))
    market = sys.argv[1] if len(sys.argv) > 1 else "BR"
    tickers = wl[market]; index = "BOVA11" if market == "BR" else "SPY"
    res = run(db, tickers, index=index)
    idx = db.conn.execute("SELECT day, close FROM prices WHERE ticker=? ORDER BY day", (index,)).fetchall()
    print(json.dumps(summarize(res, 500.0, idx), ensure_ascii=False, indent=2, default=str))
    for t in res.trades[-12:]:
        print(f"{t.entry_day} {t.ticker:7} compra {t.qty}@{t.entry:.2f} stop {t.stop:.2f} alvo {t.target:.2f} -> {t.exit_day} {t.exit:.2f} {t.reason:5} pnl {t.pnl:+.2f}")
