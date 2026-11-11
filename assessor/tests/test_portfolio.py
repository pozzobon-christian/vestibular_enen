from datetime import date
import pytest
from advisor.portfolio import Ledger, Trade, WeeklyCycle, PaperBroker, Order
from advisor.portfolio.broker import RiskGate
from advisor.risk import RiskBudget, LeveragePolicy


def test_ledger_positions_and_pnl(tmp_path):
    led = Ledger(tmp_path / "trades.jsonl")
    led.record(Trade("2025-01-06T10:00:00+00:00", "PETR4", "BR", "buy", 100, 30.0, thesis="t"))
    led.record(Trade("2025-01-07T10:00:00+00:00", "PETR4", "BR", "buy", 100, 32.0, thesis="t"))
    led.record(Trade("2025-01-08T10:00:00+00:00", "PETR4", "BR", "sell", 150, 33.0, fees=1.0, thesis="t"))
    pos = led.positions()["PETR4"]
    assert pos.quantity == 50 and pos.avg_price == pytest.approx(31.0)
    assert pos.realized_pnl == pytest.approx(150 * 2.0 - 1.0)
    reloaded = Ledger(tmp_path / "trades.jsonl")
    assert len(reloaded.trades) == 3
    with pytest.raises(ValueError):
        led.record(Trade("2025-01-09T10:00:00+00:00", "X", "BR", "buy", 1, 1, thesis=""))


def test_weekly_cycle():
    b = RiskBudget(100_000)
    wc = WeeklyCycle(b, withdraw_fraction=0.7)
    rep = wc.close_week(date(2025, 1, 8), 100_000, 104_000)
    assert rep.withdraw == pytest.approx(2800) and rep.retain == pytest.approx(1200)
    assert rep.next_week_capital == pytest.approx(101_200) and not rep.halted
    rep2 = wc.close_week(date(2025, 1, 8), 100_000, 93_000)
    assert rep2.halted and rep2.withdraw == 0


def _broker():
    b = RiskBudget(100_000, max_risk_per_trade=0.01, max_position_pct=0.2)
    gate = RiskGate(b, LeveragePolicy(100_000))
    return PaperBroker(100_000, gate)


def test_gate_rejects_bad_orders():
    br = _broker()
    r = br.place(Order("AAPL", "US", "buy", 10, 100, None, "sem stop"))
    assert not r.accepted and "stop" in r.reason
    r = br.place(Order("AAPL", "US", "buy", 500, 100, 95, "risco 2500 > 1000"))
    assert not r.accepted and "risco" in r.reason
    r = br.place(Order("AAPL", "US", "buy", 250, 100, 99.9, "notional 25000 > 20000"))
    assert not r.accepted and "tamanho" in r.reason
    r = br.place(Order("AAPL", "US", "buy", 10, 100, 95, ""))
    assert not r.accepted


def test_paper_execution_roundtrip():
    br = _broker()
    r = br.place(Order("AAPL", "US", "buy", 100, 100, 95, "tese"))
    assert r.accepted and r.filled_qty == 100
    assert br.cash < 100_000
    br.mark("AAPL", 110)
    assert br.equity() > 100_000
    r2 = br.place(Order("AAPL", "US", "sell", 100, 110, None, "realiza"))
    assert r2.accepted
    assert br.equity() == pytest.approx(100_000 + 100 * 10 - 100 * 100 * 0.0005 * 2 - 100*100*0.0003 - 100*110*0.0003, rel=1e-3)
