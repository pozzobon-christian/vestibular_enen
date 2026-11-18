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
    for name in dt.THESES:
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
