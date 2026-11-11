import random
from datetime import datetime, timedelta, timezone
from advisor.signals import find_analogs, short_setups, parse_intraday
from advisor.signals.intraday import IntraBar
from advisor.data.fundamentals_feed import _num


def _closes(n=600, seed=1):
    random.seed(seed); c = [100.0]
    for i in range(n):
        c.append(c[-1] * (1 + 0.0003 + random.gauss(0, 0.012)))
    return c


def test_analogs_returns_distribution():
    c = _closes()
    res = find_analogs("X", c, k=10)
    assert res is not None and res.n == 10 and 20 in res.horizons
    h = res.horizons[20]
    assert 0 <= h["p_positivo"] <= 1 and h["pior"] <= h["mediana"] <= h["melhor"]
    assert len(res.state) == 8 and res.examples[0]["distancia"] <= res.examples[-1]["distancia"]
    assert find_analogs("Y", c[:150]) is None


def _day(d, opens, vols, start_hour=13):
    out = []
    for i, (o, v) in enumerate(zip(opens, vols)):
        ts = datetime(2026, 11, d, start_hour, 0, tzinfo=timezone.utc) + timedelta(minutes=15 * i)
        out.append(IntraBar(ts, o, o * 1.004, o * 0.996, o * 1.002, v))
    return out


def test_short_setup_breakout_and_gap():
    prev = _day(10, [50, 50.1, 50.2, 50.1, 50.0], [100] * 5)
    today = _day(11, [51.2, 51.3, 51.9, 52.3], [150, 160, 300, 320])   # gap +2.4%, rompe a faixa de abertura
    st = short_setups("WEGE3", prev + today, atr_daily=1.5, proxy_move_pct=0.02)
    assert st.kind == "rompimento_faixa_alta" and st.direction == "compra"
    assert st.gap_pct > 0.02 and st.volume_ratio > 1.8 and st.stop == round(st.opening_range[0], 2)
    assert st.target == round(st.last + 1.5, 2)
    quiet = _day(11, [50.05, 50.0, 50.05], [90, 90, 90])
    st2 = short_setups("WEGE3", prev + quiet, atr_daily=1.5)
    assert st2.kind == "nenhum" and st2.direction == "neutro"


def test_parse_intraday_and_num():
    data = {"chart": {"result": [{"timestamp": [1762866000], "indicators": {"quote": [{"open": [10], "high": [11], "low": [9], "close": [10.5], "volume": [5]}]}}]}}
    bars = parse_intraday(data)
    assert len(bars) == 1 and bars[0].close == 10.5
    assert _num({"a": {"raw": 3.0}}, "a") == 3.0 and _num({}, "b", default=7) == 7


def test_calendar_rules():
    from advisor.calendar import build_calendar, recurring
    from datetime import date
    ev = recurring(date(2026, 11, 2), date(2026, 12, 15))
    names = {e.evento for e in ev}
    assert any("Focus" in n for n in names) and any("Payroll" in n for n in names) and any("IPCA do mês" in n for n in names)
    assert any(e.evento.startswith("Vencimento mensal") and e.data == "2026-11-20" for e in ev)
    assert any("Payroll" in e.evento and e.data == "2026-12-04" for e in ev)
    cal = build_calendar([], days_ahead=40, with_earnings=False)
    assert cal == sorted(cal, key=lambda e: (e["data"], e["hora_brt"]))
    assert all({"data", "evento", "ativos", "o_que_esperar", "preparacao"} <= set(e) for e in cal)
