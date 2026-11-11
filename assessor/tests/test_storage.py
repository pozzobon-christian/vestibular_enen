from datetime import datetime, timezone, timedelta, date
from advisor.storage import MonitorDB
from advisor.influencers import Post, detect_campaigns, herd_signal
from advisor.data.market import PriceBar


def test_db_roundtrip(tmp_path):
    db = MonitorDB(tmp_path / "m.db")
    t0 = datetime(2025, 3, 3, 12, tzinfo=timezone.utc)
    posts = [Post("@a", "x", t0, "MGLU3 compra 🚀", url="u1", engagement=10),
             Post("@b", "x", t0 + timedelta(minutes=5), "MGLU3 comprei", url="u2"),
             Post("@c", "x", t0 + timedelta(minutes=9), "MGLU3 oportunidade", url="u3")]
    assert db.upsert_posts(posts) == 3
    assert db.upsert_posts(posts) == 0            # idempotente
    back = db.posts_since(t0 - timedelta(days=1))
    assert len(back) == 3 and back[0].tickers == ["MGLU3"] and back[0].stance == "compra"
    bars = [PriceBar(date(2025, 3, 3) + timedelta(days=i), 10, 11, 9, 10 + i, 100) for i in range(5)]
    db.upsert_prices("MGLU3", "BR", bars)
    assert db.closes("MGLU3")[-1] == (date(2025, 3, 7), 14)
    camps = detect_campaigns(back, 24, 3)
    db.save_campaigns(camps)
    db.save_signal(camps[0], herd_signal(camps[0], {}))
    db.save_stats({"x:a": {"chamadas": 1}})
    assert db.latest_stats()["x:a"]["chamadas"] == 1
    db.log_run("2025-03-03T00:00:00+00:00", "test", 3, [])
    counts = db.export_jsonl(tmp_path / "exp")
    assert counts["posts"] == 3 and counts["campaigns"] == 1 and counts["herd_signals"] == 1
    s = db.summary()
    assert s["posts"] == 3 and s["campanhas"] == 1 and s["precos"] == 5


def test_monitor_analyze_offline(tmp_path, monkeypatch):
    from advisor import monitor
    monkeypatch.chdir(tmp_path)
    db = MonitorDB("data/monitor.db")
    now = datetime.now(timezone.utc)
    db.upsert_posts([Post(f"@u{i}", "x", now - timedelta(hours=i), "PETR4 compra", url=f"p{i}") for i in range(4)])
    rep = monitor.analyze(db, days=30)
    assert rep["posts_na_janela"] == 4 and len(rep["campanhas"]) == 1
    assert (tmp_path / "data/relatorio.json").exists()
