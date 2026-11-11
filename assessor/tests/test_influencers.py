from datetime import date, datetime, timedelta, timezone
import pytest
from advisor.influencers import (Influencer, InfluencerRegistry, Post, extract_tickers, detect_stance,
                                 detect_campaigns, CoMentionGraph, clusters, evaluate_calls,
                                 influencer_stats, pump_signature, herd_signal, parse_posts_jsonl)

T0 = datetime(2025, 3, 3, 12, 0, tzinfo=timezone.utc)


def _p(author, minutes, text, eng=100, platform="x"):
    return Post(author=author, platform=platform, ts=T0 + timedelta(minutes=minutes), text=text, engagement=eng)


def test_extract_and_stance():
    assert extract_tickers("Comprei PETR4 e HGLG11, olho em $AAPL e bitcoin") == ["PETR4", "HGLG11", "AAPL", "BTC"]
    assert detect_stance("Comprei PETR4, oportunidade 🚀") == "compra"
    assert detect_stance("Zerei VALE3, esticada demais, cuidado") == "venda"
    assert detect_stance("Resultado da PETR4 sai amanhã") == "neutro"
    assert detect_stance("não é hora de comprar PETR4") == "venda"


def test_registry_roundtrip(tmp_path):
    reg = InfluencerRegistry(tmp_path / "inf.json")
    reg.add(Influencer("@alpha", "x", "BR", groups=["grupo-a"], focus=["acoes_br"]))
    reg.add(Influencer("beta", "youtube", "BR", groups=["grupo-a"]))
    reg2 = InfluencerRegistry(tmp_path / "inf.json")
    assert len(reg2.all()) == 2
    assert reg2.by_group()["grupo-a"] == ["x:alpha", "youtube:beta"]
    assert reg2.get("x:alpha").focus == ["acoes_br"]


def _campaign_posts():
    return [
        _p("lider", 0, "Entrando em MGLU3 agora, alvo 15 🚀", 5000),
        _p("seg1", 20, "MGLU3 comprei também, vai subir", 800),
        _p("seg2", 45, "oportunidade em MGLU3, compra", 300),
        _p("seg3", 90, "MGLU3 compra", 100),
        _p("outro", 60, "VALE3 resultado hoje", 50),
        _p("lider", 24 * 60 * 3, "Entrando em CVCB3 🚀", 5000),
        _p("seg1", 24 * 60 * 3 + 30, "CVCB3 comprei", 800),
        _p("seg2", 24 * 60 * 3 + 50, "CVCB3 compra", 300),
    ]


def test_detect_campaigns_and_network():
    posts = _campaign_posts()
    camps = detect_campaigns(posts, window_hours=24, min_authors=3)
    assert [c.ticker for c in camps] == ["MGLU3", "CVCB3"]
    c = camps[0]
    assert c.leader == "x:lider" and c.n_authors == 4 and c.reach == 6200
    assert c.authors == ["x:lider", "x:seg1", "x:seg2", "x:seg3"]
    assert c.lag_minutes[1] == 20
    g = CoMentionGraph.from_campaigns(camps)
    assert g.weight[("x:lider", "x:seg1")] == 2
    assert g.leaders()[0][0] == "x:lider"
    cl = clusters(g, min_weight=2)
    assert cl == [["x:lider", "x:seg1", "x:seg2"]]


def _prices(path):
    d0 = date(2025, 3, 3)
    return {"MGLU3": [(d0 + timedelta(days=i), p) for i, p in enumerate(path)]}


def test_track_record_and_pump_signature():
    posts = [_p("lider", 0, "MGLU3 compra 🚀")]
    pump = [10, 11, 11.5, 11, 10.5, 10] + [9.5] * 20       # sobe 1d, devolve em 20d
    outs = evaluate_calls(posts, _prices(pump))
    assert len(outs) == 1
    o = outs[0]
    assert o.ret_1d == pytest.approx(0.10) and o.ret_20d < 0
    assert o.hit("ret_1d") is True and o.hit("ret_20d") is False
    assert pump_signature(outs) == 1.0
    st = influencer_stats(outs)["x:lider"]
    assert st["chamadas"] == 1 and st["assinatura_pump"] == 1.0
    assert evaluate_calls(posts, _prices([10, 11]))[0].ret_5d is None


def test_herd_signal_phases():
    camps = detect_campaigns(_campaign_posts(), 24, 3)
    c = camps[0]
    stats = {"x:lider": {"acerto_5d": 0.6, "chamadas": 20, "assinatura_pump": 0.1}}
    s = herd_signal(c, stats, now=c.end)
    assert s.phase == "inicio" and s.direction == "compra"
    s = herd_signal(c, stats, now=c.end, crowded_authors=4)
    assert s.phase == "lotada"
    s = herd_signal(c, stats, now=c.end, price_vs_peak=0.90)
    assert s.phase == "reversao" and "venda" in s.action
    pump_stats = {"x:lider": {"acerto_5d": 0.5, "chamadas": 20, "assinatura_pump": 0.8}}
    s = herd_signal(c, pump_stats, now=c.end)
    assert s.phase == "inicio" and "scalp" in s.action and s.confidence <= 0.6
    s = herd_signal(c, pump_stats, now=c.end, mentions_trend=0.4)
    assert s.phase == "reversao" and s.confidence > 0.3


def test_parse_posts_jsonl(tmp_path):
    f = tmp_path / "posts.jsonl"
    f.write_text('{"author":"a","platform":"x","ts":"2025-03-03T12:00:00+00:00","text":"PETR4 compra"}\n', encoding="utf-8")
    posts = parse_posts_jsonl(f)
    assert posts[0].tickers == ["PETR4"] and posts[0].stance == "compra"


def test_youtube_videos_page_parser(monkeypatch):
    from advisor.influencers import collectors
    html = ('{"videoRenderer":{"videoId":"abcdefghijk","title":{"runs":[{"text":"PETR4 vai subir? Compra agora"}]},'
            '"publishedTimeText":{"simpleText":"há 2 dias"},"viewCountText":{"simpleText":"12.345 visualizações"}}}'
            '{"videoRenderer":{"videoId":"zzzzzzzzzzz","title":{"runs":[{"text":"Outro"}]}}}')
    class R:
        status_code = 200; text = html
        def raise_for_status(self): pass
    monkeypatch.setattr(collectors, "_req", lambda: type("Q", (), {"get": staticmethod(lambda *a, **k: R())}))
    posts = collectors.youtube_channel_videos_page("UCx")
    assert len(posts) == 2 and posts[0].tickers == ["PETR4"] and posts[0].engagement == 12345
    assert posts[0].url.endswith("abcdefghijk") and posts[0].stance == "compra"
    assert (datetime.now(timezone.utc) - posts[0].ts).days == 2
