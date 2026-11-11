import math
from datetime import date, datetime, timedelta, timezone
from advisor.signals import trend_report, slope_tstat, adx, news_signals, event_study
from advisor.storage import MonitorDB
from advisor.data.market import PriceBar
from advisor import news


def _series(n=260, drift=0.001, seed=7):
    import random
    random.seed(seed)
    c = [100.0]
    for _ in range(n):
        c.append(c[-1] * (1 + drift + random.gauss(0, 0.01)))
    h = [x * 1.01 for x in c]; l = [x * 0.99 for x in c]
    return h, l, c


def test_trend_up_vs_down():
    h, l, c = _series(drift=0.002)
    up = trend_report("UP", h, l, c)
    assert up.direction == "alta" and up.tstat > 2 and up.score >= 50 and up.above_sma50
    h, l, c = _series(drift=-0.002, seed=3)
    dn = trend_report("DN", h, l, c)
    assert dn.direction == "baixa" and dn.tstat < -2
    assert adx(h, l, c) is not None
    slope, t = slope_tstat([100.0] * 80)
    assert abs(slope) < 1e-6


def test_event_study_and_news_signal(tmp_path):
    db = MonitorDB(tmp_path / "m.db")
    db.conn.executescript(news.SCHEMA)
    d0 = date(2026, 1, 5)
    closes = [100.0]
    for i in range(1, 80):
        closes.append(closes[-1] * (1.02 if i % 7 == 1 else 1.0))   # salto no dia seguinte a cada notícia
    db.upsert_prices("ACME", "US", [PriceBar(d0 + timedelta(days=i), c, c, c, c, 1) for i, c in enumerate(closes)])
    now = datetime.now(timezone.utc)
    rows = []
    for k in range(10):
        pub = datetime(2026, 1, 5, tzinfo=timezone.utc) + timedelta(days=7 * k)
        rows.append((f"u{k}", "Reuters", "imprensa", "US", "ACME beats record", "", pub.isoformat(), '["ACME"]', 0.6, "x"))
    rows.append(("fresh1", "Reuters", "imprensa", "US", "ACME record profit beat", "", now.isoformat(), '["ACME"]', 0.6, "x"))
    rows.append(("fresh2", "CNBC", "imprensa", "US", "ACME surge on strong growth", "", now.isoformat(), '["ACME"]', 0.5, "x"))
    rows.append(("lone", "Blog", "alternativa", "US", "XYZ crash", "", now.isoformat(), '["XYZ"]', -0.8, "x"))
    db.conn.executemany("INSERT INTO news VALUES (?,?,?,?,?,?,?,?,?,?)", rows); db.conn.commit()
    ev = event_study(db, "ACME")
    assert ev.n_pos >= 8 and ev.ret1_after_pos and ev.ret1_after_pos > 0.01
    sig = {s.ticker: s for s in news_signals(db, hours=24)}
    assert sig["ACME"].action == "compra" and sig["ACME"].n_sources == 2
    assert sig["XYZ"].action == "ignorar"
