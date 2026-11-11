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


def test_report_markdown(tmp_path, monkeypatch):
    from advisor import monitor, report
    monkeypatch.chdir(tmp_path)
    db = MonitorDB("data/monitor.db")
    now = datetime.now(timezone.utc)
    db.upsert_posts([Post(f"@u{i}", "x", now - timedelta(hours=i), "PETR4 compra", url=f"p{i}") for i in range(3)])
    db.log_run(now.isoformat(), "t", 3, ["x: erro"])
    monitor.analyze(db, 30)
    text = report.build("data/monitor.db")
    assert "PETR4" in text and "1 erros" in text and (tmp_path / "data/RELATORIO.md").exists()


def test_news_and_dashboard(tmp_path, monkeypatch):
    import json
    from advisor import monitor, news
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data/watchlist.json").write_text(json.dumps({"BR": ["PETR4"], "US": [], "cripto": []}), encoding="utf-8")
    (tmp_path / "data/plano.json").write_text(json.dumps({"meta_brl": 5000}), encoding="utf-8")
    (tmp_path / "data/carteira.json").write_text(json.dumps({"aportes": [{"data": "2026-11-11", "valor_brl": 500}],
        "trades": [{"data": "2026-11-12", "ticker": "PETR4", "mercado": "BR", "lado": "buy", "quantidade": 5, "preco": 30, "tese": "t"}]}), encoding="utf-8")
    db = MonitorDB("data/monitor.db")
    db.upsert_prices("PETR4", "BR", [PriceBar(date(2026, 11, 12), 30, 31, 29, 33, 100)])
    db.conn.executescript(news.SCHEMA)
    db.conn.execute("INSERT INTO news VALUES (?,?,?,?,?,?,?,?,?,?)", ("http://n/1", "InfoMoney", "imprensa", "BR",
                    "PETR4 sobe com recorde", "", "2026-11-12T10:00:00+00:00", '["PETR4"]', 0.5, "x"))
    db.conn.commit()
    now = datetime.now(timezone.utc)
    db.upsert_posts([Post(f"@u{i}", "x", now - timedelta(hours=i), "PETR4 compra", url=f"p{i}") for i in range(3)])
    monitor.analyze(db, 30)
    data = monitor.build_dashboard_data(db, tmp_path / "data/dashboard-data.json")
    cart = data["carteira"]
    assert cart["aportes_brl"] == 500 and cart["caixa_brl"] == 350 and cart["investido_brl"] == 165
    assert cart["patrimonio_brl"] == 515 and cart["posicoes"][0]["pnl_brl"] == 15
    assert data["noticias"][0]["titulo"].startswith("PETR4") and data["cotacoes"][0]["ticker"] == "PETR4"
    assert len(data["campanhas"]) == 1
