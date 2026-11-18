from advisor import strategies as st
from advisor.cases import Bar


def _bars(n=400):
    out = []; p = 100.0
    for i in range(n):
        o = p; p = p * (1.001 if (i // 50) % 2 == 0 else 0.999)
        out.append(Bar(f"2020-{1 + (i // 21) % 12:02d}-{1 + i % 21:02d}" if False else f"{2016 + i // 252}-{1 + (i % 252) // 21:02d}-{1 + i % 21:02d}", o, max(o, p), min(o, p), p))
    return out


def test_curves_and_metrics():
    b = _bars(); cdi = {x.day: 0.0004 for x in b}
    for curve in (st.buy_hold(b), st.overnight(b), st.tsmom(b, cdi), st.trend_ma(b, 50), st.covered_call(b, cdi), st.cdi_curve([x.day for x in b], cdi)):
        assert len(curve) > 10 and all(v > 0 for _, v in curve)
        m = st._metrics(curve, cdi)
        assert set(m) >= {"retorno_total", "ao_ano", "queda_maxima"}
    cc = st.covered_call(b, cdi)
    assert cc[-1][1] > 0


def test_orchestrator_sessions_and_tasks():
    from datetime import datetime, timezone
    from advisor import orchestrator as o
    wed_11h_brt = datetime(2026, 11, 18, 14, 0, tzinfo=timezone.utc)   # 11h BRT, 9h NY
    s = o.sessions(wed_11h_brt)
    assert s["b3_aberta"] and not s["eua_abertos"] and s["cripto"]
    assert set(o.due_tasks(wed_11h_brt)) == {"cripto", "b3_intradia"}
    sat = datetime(2026, 11, 21, 15, 0, tzinfo=timezone.utc)
    assert o.due_tasks(sat) == ["cripto"]
    close = datetime(2026, 11, 18, 20, 40, tzinfo=timezone.utc)        # 17h40 BRT
    assert "efeito_noite" in o.due_tasks(close)
