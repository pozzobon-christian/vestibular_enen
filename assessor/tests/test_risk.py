import pytest
from advisor.risk import (RiskBudget, position_size, kelly_fraction, risk_of_ruin,
                          LeveragePolicy, max_drawdown, sharpe_ratio, value_at_risk, expected_shortfall)


def test_position_size_by_risk():
    b = RiskBudget(100_000, max_risk_per_trade=0.01)
    ps = position_size(b, entry=30.0, stop=28.5)
    assert ps.quantity == 666
    assert ps.risk_amount <= 1000
    assert ps.capped_by == "risco"


def test_position_size_capped_by_max_position():
    b = RiskBudget(100_000, max_position_pct=0.10)
    ps = position_size(b, entry=100.0, stop=99.9)  # stop muito curto -> muitas ações
    assert ps.capped_by == "posicao_max"
    assert ps.notional <= 10_000


def test_position_size_lot():
    b = RiskBudget(100_000)
    ps = position_size(b, 30.0, 28.5, lot=100)
    assert ps.quantity == 600


def test_risk_exceeding_budget_rejected():
    b = RiskBudget(100_000, max_risk_per_trade=0.01)
    with pytest.raises(ValueError):
        position_size(b, 30, 29, risk_fraction=0.05)


def test_budget_validation():
    with pytest.raises(ValueError):
        RiskBudget(100_000, max_risk_per_trade=0.05, max_risk_per_day=0.03)


def test_kelly():
    assert kelly_fraction(0.55, 1.0, fraction=1.0) == pytest.approx(0.10)
    assert kelly_fraction(0.40, 1.0) == 0.0
    assert kelly_fraction(0.5, 2.0, fraction=0.5) == pytest.approx(0.125)


def test_risk_of_ruin_monotone():
    assert risk_of_ruin(0.4, 0.01) == 1.0
    assert risk_of_ruin(0.55, 0.01) < risk_of_ruin(0.55, 0.05)


def test_leverage_only_on_profit():
    pol = LeveragePolicy(principal=100_000, max_multiplier=2.0, profit_buffer=0.3)
    d = pol.evaluate(equity=100_000, requested_notional=120_000)
    assert not d.allowed
    d = pol.evaluate(equity=110_000, requested_notional=112_000)
    assert d.allowed
    assert d.max_leveraged_notional == pytest.approx(100_000 + 7_000 * 2)
    d = pol.evaluate(equity=110_000, requested_notional=130_000)
    assert not d.allowed


def test_metrics():
    assert max_drawdown([100, 120, 90, 130, 65]) == pytest.approx(0.5)
    r = [0.01, -0.005, 0.02, -0.01, 0.015]
    assert sharpe_ratio(r) > 0
    assert value_at_risk([-0.05, -0.02, 0.01, 0.03, 0.02], 0.8) == pytest.approx(0.05)
    assert expected_shortfall([-0.05, -0.02, 0.01, 0.03, 0.02], 0.6) == pytest.approx(0.035)
