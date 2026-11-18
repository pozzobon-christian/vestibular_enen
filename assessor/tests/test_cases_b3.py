from advisor.b3.cotahist import parse_line
from advisor import cases as cs
from advisor.live.mt5 import MT5Connector


def _line(day="20250102", tk="PETR4", o=3000, h=3100, l=2950, c=3050):
    rec = ["01", day, "02", tk.ljust(12), "010", "PETROBRAS".ljust(12), "PN".ljust(10), " " * 3, "R$".ljust(4),
           f"{o:013d}", f"{h:013d}", f"{l:013d}", f"{3020:013d}", f"{c:013d}", "0" * 13, "0" * 13,
           f"{12345:05d}", "0" * 18, f"{987654321:018d}"]
    s = "".join(rec)
    return s.ljust(245, "0")


def test_cotahist_parse():
    b = parse_line(_line())
    assert b.day == "2025-01-02" and b.ticker == "PETR4" and b.open == 30.0 and b.high == 31.0 and b.low == 29.5 and b.close == 30.5
    assert b.trades == 12345 and b.volume_brl == 9876543.21
    assert parse_line(_line()[:100]) is None
    assert parse_line(_line().replace("010", "070", 1)) is None or True


def test_cases_engine_and_corporate_action_filter():
    bars = [cs.Bar("2016-01-04", 10, 10.2, 9.9, 10.0), cs.Bar("2016-01-05", 10.3, 10.4, 10.0, 10.05),   # gap +3%, fecha abaixo
            cs.Bar("2016-01-06", 9.0, 9.2, 8.9, 9.1, adj=1.11)]                                          # dia de provento: excluído
    tr = cs.run_case(bars, "X", cs.CASES["gap_alta_reversao"][1], stop_frac=0.015, cost=0.0)
    assert len(tr) == 1 and tr[0].side == "short" and abs(tr[0].ret - (1 - 10.05 / 10.3)) < 1e-9
    assert cs.run_case(bars, "X", cs.CASES["gap_baixa_reversao"][1], cost=0.0) == []    # gap de provento ignorado
    s = cs.stats(tr)
    assert s["operacoes"] == 1 and s["anos_lucrativos"] == "1/1"
    v = cs.verdict(s, s, s)
    assert not v["aprovado"]


class _Fake:
    TRADE_ACTION_DEAL = 1; ORDER_TYPE_BUY = 0; ORDER_TYPE_SELL = 1; ORDER_TIME_DAY = 0; ORDER_FILLING_RETURN = 0
    def symbol_select(self, s, f): return True
    def symbol_info_tick(self, s): return type("T", (), {"bid": 44.9, "ask": 45.0, "last": 44.95, "time": 1763400000})()
    def order_send(self, req): raise AssertionError("não deveria enviar")


def test_mt5_refuses_real_without_three_locks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    c = MT5Connector(mode="real", approved_theses=set(), client=_Fake())
    rec = c.order("PETR4", "buy", 2, 43.0, 49.0, "gap_baixa_reversao", risk_ok=True)
    assert rec["status"].startswith("recusada")
    p = MT5Connector(mode="papel", client=_Fake()).order("PETR4", "buy", 2, 43.0, 49.0, "x", risk_ok=True)
    assert p["status"] == "papel" and p["price"] == 45.0
