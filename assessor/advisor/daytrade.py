"""Laboratório de day trade (cripto, Bybit): teses codificadas, backtest com
custos reais, critérios de aprovação e paper trading.

Fluxo obrigatório: backtest (in-sample e out-of-sample) -> critérios -> paper
trading por 2 semanas -> real com R$ 50. Nenhuma etapa pula.

Dados: Bybit v5 public (sem chave): klines de 1/15 min, funding, open interest.
Custos: taker 0,055% por lado + slippage 0,02% por lado (perpétuos Bybit).
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

FEE = 0.00055
SLIP = 0.0002
COST_RT = 2 * (FEE + SLIP)   # ida e volta


@dataclass
class Bar:
    ts: int        # ms
    o: float; h: float; l: float; c: float; v: float


# ------------------------------------------------------------------ dados
def fetch_klines(symbol: str = "BTCUSDT", interval: str = "15", days: int = 120, category: str = "linear") -> list[Bar]:
    import requests
    out: list[Bar] = []
    end = int(time.time() * 1000)
    start_limit = end - days * 86400_000
    while end > start_limit:
        r = requests.get("https://api.bybit.com/v5/market/kline",
                         params={"category": category, "symbol": symbol, "interval": interval, "end": end, "limit": 1000},
                         timeout=20, headers={"User-Agent": "assessor-investimentos/0.1"})
        r.raise_for_status()
        rows = r.json()["result"]["list"]
        if not rows:
            break
        for ts, o, h, l, c, v, _ in rows:
            out.append(Bar(int(ts), float(o), float(h), float(l), float(c), float(v)))
        end = int(rows[-1][0]) - 1
        time.sleep(0.15)
    out.sort(key=lambda b: b.ts)
    seen = set(); dedup = []
    for b in out:
        if b.ts not in seen:
            seen.add(b.ts); dedup.append(b)
    return dedup


def fetch_funding(symbol: str = "BTCUSDT", days: int = 120) -> list[tuple[int, float]]:
    import requests
    out = []
    end = int(time.time() * 1000)
    start_limit = end - days * 86400_000
    while end > start_limit:
        r = requests.get("https://api.bybit.com/v5/market/funding/history",
                         params={"category": "linear", "symbol": symbol, "endTime": end, "limit": 200}, timeout=20)
        r.raise_for_status()
        rows = r.json()["result"]["list"]
        if not rows:
            break
        for row in rows:
            out.append((int(row["fundingRateTimestamp"]), float(row["fundingRate"])))
        end = int(rows[-1]["fundingRateTimestamp"]) - 1
        time.sleep(0.15)
    return sorted(set(out))


def save_bars(bars: list[Bar], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(b) for b in bars]), encoding="utf-8")


def load_bars(path: Path) -> list[Bar]:
    return [Bar(**b) for b in json.loads(path.read_text(encoding="utf-8"))]


# ------------------------------------------------------------------ indicadores
def atr(bars: list[Bar], n: int = 14) -> list[float | None]:
    trs = []
    for i, b in enumerate(bars):
        trs.append(b.h - b.l if i == 0 else max(b.h - b.l, abs(b.h - bars[i - 1].c), abs(b.l - bars[i - 1].c)))
    out: list[float | None] = []
    s = 0.0
    for i, t in enumerate(trs):
        s += t
        if i >= n:
            s -= trs[i - n]
        out.append(s / n if i >= n - 1 else None)
    return out


def session_day(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date().isoformat()


# ------------------------------------------------------------------ teses
@dataclass
class Signal:
    side: str        # long | short
    stop: float
    target: float
    reason: str


def thesis_orb(bars: list[Bar], i: int, ctx: dict, opening_bars: int = 4, atr_stop: float = 1.0, rr: float = 2.0) -> Signal | None:
    """Rompimento da faixa de abertura: primeiros `opening_bars` candles do dia
    (UTC, 15 min cada = 1h). Rompe a máxima -> long, a mínima -> short.
    Uma operação por dia."""
    day = session_day(bars[i].ts)
    day_bars = [b for b in bars[max(0, i - 120):i + 1] if session_day(b.ts) == day]
    if len(day_bars) <= opening_bars or ctx.get("last_day") == day:
        return None
    orh = max(b.h for b in day_bars[:opening_bars]); orl = min(b.l for b in day_bars[:opening_bars])
    a = ctx["atr"][i]
    if a is None:
        return None
    c = bars[i].c
    if c > orh:
        ctx["last_day"] = day
        return Signal("long", c - atr_stop * a, c + rr * atr_stop * a, f"rompeu faixa de abertura {orh:.0f}")
    if c < orl:
        ctx["last_day"] = day
        return Signal("short", c + atr_stop * a, c - rr * atr_stop * a, f"perdeu faixa de abertura {orl:.0f}")
    return None


def thesis_vwap_reversion(bars: list[Bar], i: int, ctx: dict, z: float = 2.0, atr_stop: float = 1.5) -> Signal | None:
    """Reversão ao VWAP do dia: preço a mais de `z` desvios do VWAP volta para ele."""
    day = session_day(bars[i].ts)
    day_bars = [b for b in bars[max(0, i - 120):i + 1] if session_day(b.ts) == day]
    if len(day_bars) < 8:
        return None
    tv = sum(b.v for b in day_bars) or 1.0
    vwap = sum(b.c * b.v for b in day_bars) / tv
    var = sum(b.v * (b.c - vwap) ** 2 for b in day_bars) / tv
    sd = math.sqrt(var) if var > 0 else 0.0
    a = ctx["atr"][i]
    if sd == 0 or a is None:
        return None
    c = bars[i].c; dev = (c - vwap) / sd
    if dev > z:
        return Signal("short", c + atr_stop * a, vwap, f"{dev:.1f} desvios acima do VWAP")
    if dev < -z:
        return Signal("long", c - atr_stop * a, vwap, f"{dev:.1f} desvios abaixo do VWAP")
    return None


def thesis_momentum_breakout(bars: list[Bar], i: int, ctx: dict, lookback: int = 20, atr_stop: float = 1.0, rr: float = 2.0, vol_mult: float = 1.5) -> Signal | None:
    """Rompimento da máxima/mínima de `lookback` candles com volume acima de
    `vol_mult` x a média: seguir o movimento."""
    if i < lookback + 1:
        return None
    win = bars[i - lookback:i]
    hi = max(b.h for b in win); lo = min(b.l for b in win)
    avg_v = sum(b.v for b in win) / lookback
    a = ctx["atr"][i]
    if a is None or bars[i].v < vol_mult * avg_v:
        return None
    c = bars[i].c
    if c > hi:
        return Signal("long", c - atr_stop * a, c + rr * atr_stop * a, f"rompeu máxima de {lookback} candles com volume {bars[i].v / avg_v:.1f}x")
    if c < lo:
        return Signal("short", c + atr_stop * a, c - rr * atr_stop * a, f"perdeu mínima de {lookback} candles com volume {bars[i].v / avg_v:.1f}x")
    return None


def thesis_funding_contrarian(bars: list[Bar], i: int, ctx: dict, z: float = 2.0, atr_stop: float = 1.5, rr: float = 1.5) -> Signal | None:
    """Funding extremo (z-score sobre 30 períodos de 8h): comprados lotados ->
    short; vendidos lotados -> long. Só no candle seguinte ao funding."""
    fh = ctx.get("funding")
    if not fh:
        return None
    ts = bars[i].ts
    past = [f for t, f in fh if t <= ts][-31:]
    if len(past) < 31:
        return None
    last_t = max(t for t, _ in fh if t <= ts)
    if ts - last_t > 15 * 60 * 1000:   # só logo após o funding
        return None
    hist, cur = past[:-1], past[-1]
    m = sum(hist) / len(hist); sd = math.sqrt(sum((x - m) ** 2 for x in hist) / (len(hist) - 1)) or 1e-9
    zz = (cur - m) / sd
    a = ctx["atr"][i]
    if a is None:
        return None
    c = bars[i].c
    if zz > z:
        return Signal("short", c + atr_stop * a, c - rr * atr_stop * a, f"funding z={zz:.1f}: comprados lotados")
    if zz < -z:
        return Signal("long", c - atr_stop * a, c + rr * atr_stop * a, f"funding z={zz:.1f}: vendidos lotados")
    return None


THESES = {"orb": thesis_orb, "vwap": thesis_vwap_reversion, "momentum": thesis_momentum_breakout, "funding": thesis_funding_contrarian}


# ------------------------------------------------------------------ backtest
@dataclass
class DTrade:
    entry_ts: int; side: str; entry: float; stop: float; target: float; exit_ts: int = 0; exit: float = 0.0; reason: str = ""; ret: float = 0.0


def backtest(bars: list[Bar], thesis: str, funding=None, max_bars: int = 32, risk_frac: float = 0.01, **kw) -> dict:
    fn = THESES[thesis]
    ctx = {"atr": atr(bars), "funding": funding}
    trades: list[DTrade] = []
    open_t: DTrade | None = None
    equity = [1.0]
    for i in range(1, len(bars)):
        b = bars[i]
        if open_t:
            held = (b.ts - open_t.entry_ts) // (bars[1].ts - bars[0].ts)
            ex = None; why = ""
            if open_t.side == "long":
                if b.l <= open_t.stop: ex, why = open_t.stop, "stop"
                elif b.h >= open_t.target: ex, why = open_t.target, "alvo"
            else:
                if b.h >= open_t.stop: ex, why = open_t.stop, "stop"
                elif b.l <= open_t.target: ex, why = open_t.target, "alvo"
            if ex is None and held >= max_bars:
                ex, why = b.c, "tempo"
            if ex is not None:
                r = (ex / open_t.entry - 1) * (1 if open_t.side == "long" else -1) - COST_RT
                risk_unit = abs(open_t.entry - open_t.stop) / open_t.entry
                open_t.exit_ts, open_t.exit, open_t.reason, open_t.ret = b.ts, ex, why, r
                # tamanho pelo risco: perda no stop = risk_frac do capital
                size = risk_frac / risk_unit if risk_unit > 0 else 0
                equity.append(equity[-1] * (1 + r * size))
                trades.append(open_t); open_t = None
        if open_t is None:
            sig = fn(bars, i, ctx, **kw)
            if sig and abs(sig.stop - b.c) / b.c > 0.0008:
                open_t = DTrade(b.ts, sig.side, b.c, sig.stop, sig.target)
    return _stats(trades, equity, bars)


def _stats(trades: list[DTrade], equity: list[float], bars: list[Bar]) -> dict:
    n = len(trades)
    if n == 0:
        return {"operacoes": 0}
    wins = [t for t in trades if t.ret > 0]
    rets = [t.ret for t in trades]
    mean = sum(rets) / n
    sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / (n - 1)) if n > 1 else 0.0
    days = (bars[-1].ts - bars[0].ts) / 86400_000
    peak = equity[0]; mdd = 0.0
    for v in equity:
        peak = max(peak, v); mdd = max(mdd, (peak - v) / peak)
    gross_win = sum(t.ret for t in wins); gross_loss = -sum(t.ret for t in trades if t.ret <= 0)
    return {
        "operacoes": n, "por_dia": round(n / max(days, 1), 2), "acerto": round(len(wins) / n, 3),
        "retorno_medio_por_operacao": round(mean, 5), "expectancia_pct": round(mean * 100, 3),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        "sharpe_por_operacao": round(mean / sd * math.sqrt(n), 2) if sd > 0 else None,
        "retorno_total_capital": round(equity[-1] - 1, 4), "drawdown_max": round(mdd, 4),
        "saidas": {k: sum(1 for t in trades if t.reason == k) for k in ("alvo", "stop", "tempo")},
        "dias": round(days, 1), "custo_ida_volta": COST_RT,
    }


CRITERIA = {"operacoes_min": 100, "expectancia_min_pct": 0.05, "profit_factor_min": 1.3, "drawdown_max": 0.10, "oos_profit_factor_min": 1.1}


def evaluate(stats_is: dict, stats_oos: dict) -> dict:
    checks = {
        "operacoes >= 100 (in-sample)": stats_is.get("operacoes", 0) >= CRITERIA["operacoes_min"],
        "expectância >= 0,05% por operação após custos": (stats_is.get("expectancia_pct") or -1) >= CRITERIA["expectancia_min_pct"],
        "profit factor >= 1,3 (in-sample)": (stats_is.get("profit_factor") or 0) >= CRITERIA["profit_factor_min"],
        "drawdown máximo <= 10%": (stats_is.get("drawdown_max") or 1) <= CRITERIA["drawdown_max"],
        "profit factor >= 1,1 fora da amostra": (stats_oos.get("profit_factor") or 0) >= CRITERIA["oos_profit_factor_min"],
        "expectância positiva fora da amostra": (stats_oos.get("expectancia_pct") or -1) > 0,
    }
    return {"aprovada": all(checks.values()), "criterios": checks}


def run_lab(symbols=("BTCUSDT", "ETHUSDT"), days: int = 120, out_dir: Path = Path("data/daytrade")) -> dict:
    report = {"gerado_em": datetime.now(timezone.utc).isoformat(), "custos": COST_RT, "criterios": CRITERIA, "resultados": {}}
    for sym in symbols:
        bars = fetch_klines(sym, "15", days)
        save_bars(bars, out_dir / f"{sym}_15m.json")
        funding = fetch_funding(sym, days)
        (out_dir / f"{sym}_funding.json").write_text(json.dumps(funding), encoding="utf-8")
        split = int(len(bars) * 0.7)
        for name in THESES:
            is_, oos = bars[:split], bars[split - 200:]
            s_is = backtest(is_, name, funding); s_oos = backtest(oos, name, funding)
            ev = evaluate(s_is, s_oos)
            report["resultados"][f"{sym}:{name}"] = {"in_sample": s_is, "out_of_sample": s_oos, "avaliacao": ev}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "lab.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


# ------------------------------------------------------------------ paper trading
def paper_step(symbol: str, thesis: str, state_path: Path, interval: str = "15") -> dict:
    """Um passo do robô de papel: baixa os últimos candles, aplica a tese, abre
    ou fecha posição fictícia e grava em state_path. Rodar a cada 15 min."""
    bars = fetch_klines(symbol, interval, days=10)
    funding = fetch_funding(symbol, 20) if thesis == "funding" else None
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"pos": None, "trades": [], "equity": 1.0}
    ctx = {"atr": atr(bars), "funding": funding, "last_day": state.get("last_day")}
    b = bars[-1]; i = len(bars) - 1
    pos = state["pos"]
    if pos:
        ex = None; why = ""
        if pos["side"] == "long":
            if b.l <= pos["stop"]: ex, why = pos["stop"], "stop"
            elif b.h >= pos["target"]: ex, why = pos["target"], "alvo"
        else:
            if b.h >= pos["stop"]: ex, why = pos["stop"], "stop"
            elif b.l <= pos["target"]: ex, why = pos["target"], "alvo"
        if ex is None and (b.ts - pos["entry_ts"]) >= 32 * 15 * 60 * 1000:
            ex, why = b.c, "tempo"
        if ex is not None:
            r = (ex / pos["entry"] - 1) * (1 if pos["side"] == "long" else -1) - COST_RT
            risk_unit = abs(pos["entry"] - pos["stop"]) / pos["entry"]
            state["equity"] *= 1 + r * (0.01 / risk_unit)
            state["trades"].append({**pos, "exit_ts": b.ts, "exit": ex, "reason": why, "ret": r})
            state["pos"] = None
    if state["pos"] is None:
        sig = THESES[thesis](bars, i, ctx)
        if sig:
            state["pos"] = {"entry_ts": b.ts, "side": sig.side, "entry": b.c, "stop": sig.stop, "target": sig.target, "reason": sig.reason}
    state["last_day"] = ctx.get("last_day"); state["updated"] = datetime.now(timezone.utc).isoformat(); state["symbol"] = symbol; state["thesis"] = thesis
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["lab", "paper", "paper-loop"])
    ap.add_argument("--symbol", default="BTCUSDT"); ap.add_argument("--thesis", default="orb"); ap.add_argument("--days", type=int, default=120)
    a = ap.parse_args()
    if a.cmd == "lab":
        rep = run_lab(days=a.days)
        for k, v in rep["resultados"].items():
            print(k, "| IS:", {x: v["in_sample"].get(x) for x in ("operacoes", "acerto", "expectancia_pct", "profit_factor", "drawdown_max")},
                  "| OOS:", {x: v["out_of_sample"].get(x) for x in ("operacoes", "expectancia_pct", "profit_factor")}, "| aprovada:", v["avaliacao"]["aprovada"])
    elif a.cmd == "paper":
        print(json.dumps(paper_step(a.symbol, a.thesis, Path(f"data/daytrade/paper_{a.symbol}_{a.thesis}.json")), ensure_ascii=False, indent=2)[:1500])
    else:
        while True:
            try:
                st = paper_step(a.symbol, a.thesis, Path(f"data/daytrade/paper_{a.symbol}_{a.thesis}.json"))
                print(datetime.now().strftime("%H:%M"), "equity", round(st["equity"], 4), "pos", st["pos"] and st["pos"]["side"], "trades", len(st["trades"]))
            except Exception as e:  # noqa: BLE001
                print("erro:", e)
            time.sleep(15 * 60)
