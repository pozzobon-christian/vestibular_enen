"""Casos dos últimos 10 anos aplicados ao day trade.

Cada "caso" é uma condição observável ANTES da abertura (gap, dia anterior,
calendário). A operação é day trade puro: entra na abertura, sai no
fechamento do mesmo dia, com stop opcional medido pela máxima/mínima do dia
(conservador: se o dia toca stop e alvo, assume stop). Custos B3 de day trade.

Validação: 2016-2022 descobre, 2023-hoje confirma; e conta quantos anos, de
10, a tese ganhou dinheiro. Só passa o que ganha nas duas metades e na
maioria dos anos.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path

COST_BR = 2 * (0.00015 + 0.0003)          # 0,09% ida e volta (emolumentos day trade + slippage)
SPLIT_YEAR = "2023-01-01"


@dataclass
class Bar:
    day: str; o: float; h: float; l: float; c: float; adj: float = 1.0   # adj = fator de ajuste do dia (Yahoo adjclose/close)


@dataclass
class CaseTrade:
    ticker: str; day: str; side: str; entry: float; exit: float; reason: str; ret: float


def load_yahoo_daily(ticker: str, market: str = "BR", range_: str = "10y") -> list[Bar]:
    """OHLC diário de 10 anos + fator de ajuste (para detectar proventos)."""
    import requests
    from .data.market import yahoo_symbol, USER_AGENT
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol(ticker, market)}",
                     params={"range": range_, "interval": "1d"}, timeout=30, headers={"User-Agent": "Mozilla/5.0 " + USER_AGENT})
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    q = res["indicators"]["quote"][0]; adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose") or q["close"]
    from datetime import datetime, timezone
    out = []
    for i, t in enumerate(res.get("timestamp") or []):
        o, h, l, c, a = q["open"][i], q["high"][i], q["low"][i], q["close"][i], adj[i]
        if None in (o, h, l, c, a) or c <= 0 or o <= 0:
            continue
        out.append(Bar(datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat(), o, h, l, c, a / c))
    return out


def merge_official(yahoo: list[Bar], official: list) -> list[Bar]:
    """Substitui OHLC pelo COTAHIST oficial da B3 quando houver o dia; mantém o
    fator de ajuste do Yahoo para detectar proventos."""
    off = {b.day: b for b in official}
    out = []
    for b in yahoo:
        x = off.get(b.day)
        out.append(Bar(b.day, x.open, x.high, x.low, x.close, b.adj) if x and x.open > 0 else b)
    return out


# ------------------------------------------------------------------ casos
def _gap(bars, i):
    """Gap ajustado por proventos; None em dia de provento/desdobramento."""
    prev, cur = bars[i - 1], bars[i]
    if abs(cur.adj / prev.adj - 1) > 0.003:      # mudou o fator: dia ex-provento ou evento societário
        return None
    return cur.o / prev.c - 1


def _ret(bars, i):
    if abs(bars[i].adj / bars[i - 1].adj - 1) > 0.003:
        return None
    return bars[i].c / bars[i - 1].c - 1


def _first_trading_day_of_month(bars, i):
    return i > 0 and bars[i].day[:7] != bars[i - 1].day[:7]


CASES = {
    "gap_alta_reversao": ("vender na abertura quando abre >= 1,5% acima do fechamento anterior",
                          lambda b, i: "short" if (g := _gap(b, i)) is not None and g >= 0.015 else None),
    "gap_baixa_reversao": ("comprar na abertura quando abre >= 1,5% abaixo",
                           lambda b, i: "long" if (g := _gap(b, i)) is not None and g <= -0.015 else None),
    "gap_alta_continuacao": ("comprar na abertura quando abre >= 1,5% acima",
                             lambda b, i: "long" if (g := _gap(b, i)) is not None and g >= 0.015 else None),
    "gap_baixa_continuacao": ("vender na abertura quando abre >= 1,5% abaixo",
                              lambda b, i: "short" if (g := _gap(b, i)) is not None and g <= -0.015 else None),
    "apos_queda_forte": ("comprar no dia seguinte a uma queda >= 3%",
                         lambda b, i: "long" if i > 1 and (r := _ret(b, i - 1)) is not None and r <= -0.03 else None),
    "apos_alta_forte": ("vender no dia seguinte a uma alta >= 3%",
                        lambda b, i: "short" if i > 1 and (r := _ret(b, i - 1)) is not None and r >= 0.03 else None),
    "apos_alta_forte_continuacao": ("comprar no dia seguinte a uma alta >= 3%",
                                    lambda b, i: "long" if i > 1 and (r := _ret(b, i - 1)) is not None and r >= 0.03 else None),
    "primeiro_dia_do_mes": ("comprar na abertura do 1º pregão do mês (fluxo de aportes)",
                            lambda b, i: "long" if _first_trading_day_of_month(b, i) else None),
    "segunda_feira_venda": ("vender na abertura de segunda-feira",
                            lambda b, i: "short" if __import__("datetime").date.fromisoformat(b[i].day).weekday() == 0 else None),
    "sexta_feira_compra": ("comprar na abertura de sexta-feira",
                           lambda b, i: "long" if __import__("datetime").date.fromisoformat(b[i].day).weekday() == 4 else None),
}


def run_case(bars: list[Bar], ticker: str, rule, stop_frac: float | None = 0.015, cost: float = COST_BR) -> list[CaseTrade]:
    out = []
    for i in range(1, len(bars)):
        side = rule(bars, i)
        if not side:
            continue
        b = bars[i]; e = b.o
        if stop_frac:
            stop = e * (1 - stop_frac) if side == "long" else e * (1 + stop_frac)
            hit = (b.l <= stop) if side == "long" else (b.h >= stop)
        else:
            hit = False
        x, why = (stop, "stop") if hit else (b.c, "fechamento")
        r = (x / e - 1) * (1 if side == "long" else -1) - cost
        out.append(CaseTrade(ticker, b.day, side, e, x, why, r))
    return out


def stats(trades: list[CaseTrade]) -> dict:
    n = len(trades)
    if n == 0:
        return {"operacoes": 0}
    rets = [t.ret for t in trades]; mean = sum(rets) / n
    sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / (n - 1)) if n > 1 else 0.0
    gw = sum(r for r in rets if r > 0); gl = -sum(r for r in rets if r <= 0)
    years = {}
    for t in trades:
        years.setdefault(t.day[:4], []).append(t.ret)
    yr = {y: round(sum(v), 4) for y, v in sorted(years.items())}
    return {"operacoes": n, "acerto": round(sum(1 for r in rets if r > 0) / n, 3), "expectancia_pct": round(mean * 100, 3),
            "profit_factor": round(gw / gl, 2) if gl > 0 else None, "t_stat": round(mean / (sd / math.sqrt(n)), 2) if sd > 0 else None,
            "stops": sum(1 for t in trades if t.reason == "stop"),
            "anos_lucrativos": f"{sum(1 for v in yr.values() if v > 0)}/{len(yr)}", "soma_por_ano": yr}


def verdict(s_is: dict, s_oos: dict, s_all: dict) -> dict:
    pos, tot = (int(x) for x in s_all.get("anos_lucrativos", "0/1").split("/"))
    checks = {
        "200+ operações em 10 anos": s_all.get("operacoes", 0) >= 200,
        "expectância > 0,05% depois dos custos (2016-2022)": (s_is.get("expectancia_pct") or -1) > 0.05,
        "expectância > 0 fora da amostra (2023-hoje)": (s_oos.get("expectancia_pct") or -1) > 0,
        "t-stat >= 2 nos 10 anos (não é sorte)": (s_all.get("t_stat") or 0) >= 2,
        "lucrativa em 7+ de cada 10 anos": tot > 0 and pos / tot >= 0.7,
    }
    return {"aprovado": all(checks.values()), "criterios": checks}


def study(data: dict[str, list[Bar]], stop_frac: float | None = 0.015) -> dict:
    rep = {}
    for name, (desc, rule) in CASES.items():
        trades = [t for tk, bars in data.items() for t in run_case(bars, tk, rule, stop_frac)]
        is_ = [t for t in trades if t.day < SPLIT_YEAR]; oos = [t for t in trades if t.day >= SPLIT_YEAR]
        s_is, s_oos, s_all = stats(is_), stats(oos), stats(trades)
        per = {}
        for tk in data:
            st = stats([t for t in trades if t.ticker == tk])
            if st["operacoes"]:
                per[tk] = {k: st[k] for k in ("operacoes", "expectancia_pct", "anos_lucrativos")}
        rep[name] = {"descricao": desc, "2016_2022": s_is, "2023_hoje": s_oos, "10_anos": s_all,
                     "veredito": verdict(s_is, s_oos, s_all), "por_acao": per}
    return rep


TICKERS = ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "WEGE3", "PRIO3", "MGLU3", "B3SA3", "SUZB3", "RENT3", "BOVA11"]


def build(out: Path = Path("data/cases/estudo-10-anos.json"), use_official: bool = True) -> dict:
    from datetime import date
    errors = []; data = {}; sources = {}
    official = {}
    if use_official:
        from .b3.cotahist import fetch_year
        for y in range(date.today().year - 10, date.today().year + 1):
            try:
                for b in fetch_year(y, set(TICKERS)):
                    official.setdefault(b.ticker, []).append(b)
            except Exception as e:  # noqa: BLE001
                errors.append(f"COTAHIST {y}: {type(e).__name__}: {str(e)[:80]}")
    for t in TICKERS:
        try:
            yb = load_yahoo_daily(t)
            data[t] = merge_official(yb, official.get(t, [])) if official.get(t) else yb
            sources[t] = f"{'B3 COTAHIST oficial' if official.get(t) else 'Yahoo'} + fator de ajuste Yahoo; {len(data[t])} pregões de {data[t][0].day} a {data[t][-1].day}"
        except Exception as e:  # noqa: BLE001
            errors.append(f"{t}: {type(e).__name__}: {str(e)[:80]}")
    rep = {"metodo": __doc__.strip().splitlines()[0], "custo_ida_volta": COST_BR, "stop": "1,5% (pela máxima/mínima do dia, conservador)",
           "fontes": sources, "erros": errors,
           "com_stop": study(data, 0.015), "sem_stop": study(data, None)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return rep


if __name__ == "__main__":
    rep = build()
    for mode in ("com_stop", "sem_stop"):
        print("==", mode)
        for k, v in rep[mode].items():
            a, i, o = v["10_anos"], v["2016_2022"], v["2023_hoje"]
            print(f"{k:28} n={a.get('operacoes'):5} acerto={a.get('acerto')} exp={a.get('expectancia_pct')}% t={a.get('t_stat')} anos+={a.get('anos_lucrativos')} | IS exp={i.get('expectancia_pct')} OOS exp={o.get('expectancia_pct')} | {'APROVADO' if v['veredito']['aprovado'] else '-'}")
    print("fontes:", rep["fontes"]); print("erros:", rep["erros"])
