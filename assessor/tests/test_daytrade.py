import random
from advisor import daytrade as dt


def _bars(n=2000, seed=3):
    random.seed(seed); c = 60000.0; out = []
    ts = 1_760_000_000_000
    for i in range(n):
        o = c; c = c * (1 + random.gauss(0, 0.002) + (0.0004 if (i // 200) % 2 == 0 else -0.0004))
        h = max(o, c) * (1 + abs(random.gauss(0, 0.0008))); l = min(o, c) * (1 - abs(random.gauss(0, 0.0008)))
        out.append(dt.Bar(ts + i * 900_000, o, h, l, c, 100 + random.random() * 400))
    return out


def test_backtest_all_theses_run_and_cost_applied():
    bars = _bars()
    funding = [(bars[i].ts, random.gauss(0.0001, 0.0003)) for i in range(0, len(bars), 32)]
    for name in ("orb", "vwap", "momentum", "funding"):
        s = dt.backtest(bars, name, funding)
        assert "operacoes" in s
        if s["operacoes"]:
            assert set(s["saidas"]) == {"alvo", "stop", "tempo"} and s["custo_ida_volta"] == dt.COST_RT
    st = dt.backtest(bars, "orb")
    assert st["operacoes"] > 10 and st["por_dia"] <= 1.1   # uma por dia no ORB


def test_evaluate_criteria():
    good = {"operacoes": 150, "expectancia_pct": 0.1, "profit_factor": 1.5, "drawdown_max": 0.05}
    oos = {"profit_factor": 1.2, "expectancia_pct": 0.02}
    assert dt.evaluate(good, oos)["aprovada"]
    bad = dict(good, profit_factor=1.1)
    assert not dt.evaluate(bad, oos)["aprovada"]



def test_stock_eod_exit_and_costs():
    bars = _bars(n=26 * 40)   # 40 "pregões" de 26 candles de 15 min
    for k, b in enumerate(bars):  # agrupa em dias de 26 candles
        day = k // 26
        bars[k] = dt.Bar(1_760_000_000_000 + day * 86_400_000 + (k % 26) * 900_000, b.o, b.h, b.l, b.c, b.v)
    st, trades = dt.backtest(bars, "momentum", cost=dt.COSTS["BR"], eod_exit=True, return_trades=True)
    assert all(dt.session_day(t.entry_ts) == dt.session_day(t.exit_ts) for t in trades)   # nunca dorme posicionado
    assert st["custo_ida_volta"] == dt.COSTS["BR"] < dt.COSTS["cripto"]
    pooled = dt._pooled(trades, 40)
    assert pooled["operacoes"] == len(trades)



def test_intraday_momentum_and_gap_fade_enter_on_the_right_bar():
    bars = []
    base = 1_760_000_000_000
    for day in range(30):
        prev = bars[-1].c if bars else 100.0
        o = prev * (1.02 if day % 2 == 0 else 1.0)       # gap de 2% em dias pares
        for k in range(26):
            c = o * (1 + 0.001 * k)
            bars.append(dt.Bar(base + day * 86_400_000 + k * 900_000, o if k == 0 else bars[-1].c, max(o, c) * 1.001, min(o, c) * 0.999, c, 100))
    st, tr = dt.backtest(bars, "intraday_momentum", cost=0.0, eod_exit=True, return_trades=True)
    assert tr and all(dt._day_pos(bars)[[b.ts for b in bars].index(t.entry_ts)][0] == 23 for t in tr)
    assert all(t.reason == "fim_do_pregao" for t in tr)
    st2, tr2 = dt.backtest(bars, "gap_fade", cost=0.0, eod_exit=True, return_trades=True)
    assert tr2 and all(t.side == "short" for t in tr2)
