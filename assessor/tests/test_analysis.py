from datetime import datetime, timezone, timedelta
import pytest
from advisor.fundamentals import CompanyFinancials, ratios, score_company, dcf_value, graham_number
from advisor.fiis import FII, fii_score, fii_metrics
from advisor.crypto import CryptoAsset, crypto_risk_flags, funding_signal
from advisor.signals import score_text, aggregate_sentiment, SentimentItem, rsi, sma
from advisor.data.market import parse_stooq_csv, parse_rss
from advisor.data.sources import list_sources


def _company(**kw):
    base = dict(ticker="XPTO3", price=20.0, shares_outstanding=1e9, revenue=50e9, ebit=10e9,
                ebitda=12e9, net_income=6e9, equity=30e9, total_debt=10e9, cash=8e9,
                operating_cash_flow=9e9, capex=3e9, dividends_paid=2e9, revenue_growth_5y=0.10)
    base.update(kw)
    return CompanyFinancials(**base)


def test_ratios_and_score():
    c = _company()
    r = ratios(c)
    assert r["P/L"] == pytest.approx(20e9 / 6e9)
    assert r["divida_liquida/EBITDA"] == pytest.approx(2e9 / 12e9)
    s = score_company(c)
    assert 0 <= s.total <= 100 and s.total > 50
    assert s.flags == []
    bad = _company(net_income=-1e9, operating_cash_flow=-2e9, total_debt=60e9)
    sb = score_company(bad)
    assert sb.total < s.total
    assert any("alavancagem" in f for f in sb.flags)


def test_dcf_and_graham():
    v = dcf_value(fcf=100.0, growth_rates=[0.1] * 5, discount_rate=0.12, terminal_growth=0.03, shares=10)
    assert v > 0
    with pytest.raises(ValueError):
        dcf_value(100, [0.1], 0.03, 0.05, 10)
    assert graham_number(2.0, 10.0) == pytest.approx((22.5 * 20) ** 0.5)
    assert graham_number(-1, 10) is None


def test_fii_score():
    good = FII("HGLG11", 160, 170, 16.0, 1.3, "tijolo-logistica", vacancy_physical=0.03,
               num_properties=20, num_tenants=50, top_tenant_share=0.1, avg_lease_years=5,
               leverage=0.05, liquidity_daily_brl=5e6, management_fee=0.009, cdi_or_rf_ref=0.10)
    s, flags = fii_score(good)
    assert s >= 70 and flags == []
    weak = FII("RUIM11", 100, 70, 6.0, 0.5, "tijolo-lajes", vacancy_physical=0.4, num_properties=1,
               top_tenant_share=0.9, leverage=0.4, liquidity_daily_brl=50_000, management_fee=0.02)
    s2, flags2 = fii_score(weak)
    assert s2 < s and len(flags2) >= 3
    assert fii_metrics(good)["P/VP"] == pytest.approx(160 / 170)


def test_crypto_flags_and_funding():
    a = CryptoAsset("XYZ", 1.0, 1e8, 5e5, 1e8, max_supply=1e9, exchange_netflow_7d=2e6,
                    funding_rate_8h=0.0005, years_live=0.5)
    flags = crypto_risk_flags(a)
    assert any("desbloqueio" in f for f in flags)
    assert any("liquidez" in f for f in flags)
    assert any("1 ano" in f for f in flags)
    hist = [0.0001] * 30 + [0.001]
    assert funding_signal(hist) == "viés_baixa"
    assert funding_signal([0.0001] * 5) == "neutro"


def test_sentiment():
    assert score_text("Empresa supera expectativas e anuncia recompra recorde") > 0
    assert score_text("CVM abre investigação por fraude; ação desaba") < 0
    assert score_text("não houve lucro no trimestre") < 0  # negação inverte
    now = datetime.now(timezone.utc)
    items = [SentimentItem("record profit beat", "oficial", now),
             SentimentItem("crash crash crash", "reddit", now - timedelta(hours=48))]
    agg = aggregate_sentiment(items, now)
    assert agg["label"] == "positivo" and agg["n"] == 2


def test_technical():
    closes = [float(i) for i in range(1, 40)]
    assert sma(closes, 3)[2] == pytest.approx(2.0)
    assert rsi(closes)[-1] == pytest.approx(100.0)


def test_parsers():
    csv_text = "Date,Open,High,Low,Close,Volume\n2024-01-02,10,11,9,10.5,1000\nbad,row\n"
    bars = parse_stooq_csv(csv_text)
    assert len(bars) == 1 and bars[0].close == 10.5
    rss = "<rss><channel><item><title>Fato relevante</title><link>http://x</link></item></channel></rss>"
    assert parse_rss(rss)[0]["title"] == "Fato relevante"
    assert len(list_sources("oficial", "BR")) > 3


def test_sources_are_public_only():
    from advisor.data.sources import SOURCES
    assert all(s.kind in ("oficial", "alternativa") for s in SOURCES)


def test_yahoo_parser_and_youtube_regex():
    from advisor.data.market import parse_yahoo_chart
    data = {"chart": {"result": [{"timestamp": [1704153600, 1704240000],
            "indicators": {"quote": [{"open": [10, 11], "high": [11, 12], "low": [9, 10], "close": [10.5, None], "volume": [100, 200]}]}}]}}
    bars = parse_yahoo_chart(data)
    assert len(bars) == 1 and bars[0].close == 10.5 and bars[0].day.isoformat() == "2024-01-02"
    from advisor.influencers.collectors import _YT_CANON, _YT_SEARCH, _YT_EXTERNAL
    html = '<link rel="canonical" href="https://www.youtube.com/channel/UCabc_123-x">'
    assert _YT_CANON.search(html).group(1) == "UCabc_123-x"
    assert _YT_EXTERNAL.search('{"externalId":"UCzzz"}').group(1) == "UCzzz"
    page = '{"channelRenderer":{"channelId":"UC111","title":{},"navigationEndpoint":{"browseEndpoint":{"canonicalBaseUrl":"/@canal"}}}}'
    m = _YT_SEARCH.search(page)
    assert m.group(1) == "UC111" and m.group(2) == "@canal"
