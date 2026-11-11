import math
import pytest
from advisor.options import (black_scholes, greeks, implied_volatility, binomial_american,
                             bull_call_spread, iron_condor, covered_call, long_straddle, cash_secured_put)


S, K, T, R, SIG = 100.0, 100.0, 0.5, 0.05, 0.20


def test_bsm_known_values():
    # valores de referência (Hull): call ATM 6m, r=5%, sigma=20%
    assert black_scholes(S, K, T, R, SIG, "call") == pytest.approx(6.889, abs=1e-2)
    assert black_scholes(S, K, T, R, SIG, "put") == pytest.approx(4.420, abs=1e-2)


def test_put_call_parity():
    c = black_scholes(S, K, T, R, SIG, "call")
    p = black_scholes(S, K, T, R, SIG, "put")
    assert c - p == pytest.approx(S - K * math.exp(-R * T), abs=1e-9)


def test_greeks_sanity():
    g = greeks(S, K, T, R, SIG, "call")
    assert 0.5 < g.delta < 0.7
    assert g.gamma > 0 and g.vega > 0 and g.theta < 0 and g.rho > 0
    gp = greeks(S, K, T, R, SIG, "put")
    assert g.delta - gp.delta == pytest.approx(1.0, abs=1e-9)   # q = 0


def test_implied_vol_roundtrip():
    price = black_scholes(S, 105, T, R, 0.33, "put")
    assert implied_volatility(price, S, 105, T, R, "put") == pytest.approx(0.33, abs=1e-5)


def test_american_put_worth_more_than_european():
    eu = black_scholes(S, 110, T, R, SIG, "put")
    am = binomial_american(S, 110, T, R, SIG, "put", steps=300)
    assert am >= eu - 1e-9
    # call americana sem dividendos ~ europeia
    assert binomial_american(S, K, T, R, SIG, "call", steps=300) == pytest.approx(
        black_scholes(S, K, T, R, SIG, "call"), abs=0.05)


def test_bull_call_spread_payoff():
    s = bull_call_spread(30, 1.5, 33, 0.5, qty=100)
    assert s.net_cost() == pytest.approx(100.0)
    assert s.max_loss() == pytest.approx(100.0)
    assert s.max_profit() == pytest.approx(200.0)
    assert s.break_evens() == [pytest.approx(31.0, abs=1e-2)]


def test_iron_condor_defined_risk():
    s = iron_condor(90, 0.5, 95, 1.5, 105, 1.5, 110, 0.5, qty=1)
    assert s.net_cost() == pytest.approx(-2.0)   # crédito
    assert s.max_profit() == pytest.approx(2.0)
    assert s.max_loss() == pytest.approx(3.0)
    assert len(s.break_evens()) == 2


def test_covered_call_and_straddle():
    cc = covered_call(spot=30, strike=32, premium=0.8, qty=100)
    assert cc.max_profit() == pytest.approx(280.0)
    st = long_straddle(100, 5, 4, qty=1)
    assert st.max_profit() == float("inf")
    assert st.max_loss() == pytest.approx(9.0)
    csp = cash_secured_put(50, 2, qty=1)
    assert csp.max_loss() == pytest.approx(48.0)
