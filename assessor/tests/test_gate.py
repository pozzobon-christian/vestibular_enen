from advisor.signals import order_gate, stabilization, structural_stop, crypto_risk_composite


def test_btc_11_11_would_be_blocked():
    votes = {"balanco": None, "analogos": "a_favor", "noticias": None, "tendencia": "contra", "intradia": None}
    risk = crypto_risk_composite(ibit_5d=-0.068, coin_trend="baixa", mstr_trend="alta", btc_close=73721, btc_low20=73721)
    assert risk["negativo"] and risk["n"] == 3
    g = order_gate("buy", votes, "baixa", 65, "neutro", stab=False, analog_n=6, crypto_risk=risk, risk_brl=5, risk_limit_brl=10)
    assert not g.approved
    assert any("contra a tendência" in b for b in g.blockers)
    assert any("risco cripto" in b for b in g.blockers)
    assert any("votação" in b for b in g.blockers)
    assert any("n=6" in r for r in g.reasons)


def test_trend_following_buy_passes_in_defensive_regime():
    votes = {"balanco": "a_favor", "analogos": "neutro", "noticias": None, "tendencia": "a_favor", "intradia": "a_favor"}
    g = order_gate("buy", votes, "alta", 85, "defensivo", stab=False, analog_n=15, risk_brl=4.3, risk_limit_brl=10)
    assert g.approved and not g.blockers


def test_counter_trend_needs_stabilization_and_risk_limit():
    votes = {"balanco": "a_favor", "analogos": "a_favor", "noticias": None, "tendencia": "contra", "intradia": None}
    g = order_gate("buy", votes, "baixa", 70, "neutro", stab=True, analog_n=12)
    assert not g.approved and any("votação" in b for b in g.blockers)   # tendência contra ainda derruba a votação
    votes2 = {"balanco": "a_favor", "analogos": "a_favor", "noticias": "a_favor", "tendencia": "neutro", "intradia": None}
    g2 = order_gate("buy", votes2, "baixa", 70, "defensivo", stab=True, analog_n=12, risk_brl=12, risk_limit_brl=10)
    assert not g2.approved and any("risco" in b for b in g2.blockers)


def test_stabilization_and_structural_stop():
    highs = [10, 10.2, 10.1, 10.0, 9.8, 10.4]; lows = [9.5, 9.6, 9.4, 9.3, 9.2, 9.9]; closes = [9.8, 10.0, 9.7, 9.5, 9.4, 10.3]
    assert stabilization(highs, lows, closes, "compra") is True        # 10.3 > max(10.1,10.0,9.8) e > média5
    closes2 = closes[:-1] + [9.6]
    assert stabilization(highs, lows, closes2, "compra") is False
    assert structural_stop(lows, highs, closes, atr_value=0.5, side="compra") == 9.2   # min 5d (9.2) < 10.3-0.5
