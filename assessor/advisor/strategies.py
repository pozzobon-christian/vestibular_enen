"""Estratégias com evidência acadêmica, testadas em 10 anos de dados reais.

Ações (B3): efeito noite (Lou, Polk e Skouras, 2019); momentum de série
temporal no índice (Moskowitz, Ooi e Pedersen, 2012; Faber, 2007).
Opções: venda coberta sistemática (prêmio de risco de volatilidade: Whaley,
2002; Israelov e Nielsen, 2015). Sem histórico gratuito de opções da B3, o
prêmio é ESTIMADO por Black-Scholes com vol implícita = vol realizada x 1,15.
Bitcoin: seguir tendência (Detzel, Liu, Strauss, Zhou e Zhu, 2021).

Todas com custos, contra o "comprar e segurar" do mesmo ativo e contra o CDI.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

from .cases import load_yahoo_daily, Bar
from .options.pricing import black_scholes


def fetch_cdi(start: str = "2014-01-01") -> dict[str, float]:
    """CDI diário (taxa do dia, em fração) do Banco Central, série SGS 12."""
    import requests
    d0 = date.fromisoformat(start).strftime("%d/%m/%Y"); out = {}
    y = date.fromisoformat(start).year
    while y <= date.today().year:   # API limita janelas de 10 anos; vai ano a ano
        r = requests.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados",
                         params={"formato": "json", "dataInicial": f"01/01/{y}", "dataFinal": f"31/12/{y}"}, timeout=30)
        if r.ok:
            for row in r.json():
                dd, mm, yy = row["data"].split("/")
                out[f"{yy}-{mm}-{dd}"] = float(row["valor"]) / 100
        y += 1
    return out


def _metrics(curve: list[tuple[str, float]], cdi: dict[str, float] | None = None) -> dict:
    if len(curve) < 2:
        return {}
    v0, v1 = curve[0][1], curve[-1][1]
    years = (date.fromisoformat(curve[-1][0]) - date.fromisoformat(curve[0][0])).days / 365.25
    cagr = (v1 / v0) ** (1 / years) - 1 if years > 0 else 0
    rets = [curve[i][1] / curve[i - 1][1] - 1 for i in range(1, len(curve))]
    m = sum(rets) / len(rets); sd = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))
    rf = (sum(cdi.get(curve[i][0], 0.0) for i in range(1, len(curve))) / len(rets)) if cdi else 0.0
    peak = v0; mdd = 0.0
    for _, v in curve:
        peak = max(peak, v); mdd = max(mdd, (peak - v) / peak)
    return {"retorno_total": round(v1 / v0 - 1, 3), "ao_ano": round(cagr, 4), "queda_maxima": round(mdd, 3),
            "sharpe": round((m - rf) / sd * math.sqrt(252), 2) if sd > 0 else None, "anos": round(years, 1)}


def buy_hold(bars: list[Bar]) -> list[tuple[str, float]]:
    """Comprar e segurar com proventos reinvestidos (fechamento ajustado)."""
    return [(b.day, b.c * b.adj / (bars[0].c * bars[0].adj)) for b in bars]


def cdi_curve(days: list[str], cdi: dict[str, float]) -> list[tuple[str, float]]:
    v = 1.0; out = [(days[0], 1.0)]
    for d in days[1:]:
        v *= 1 + cdi.get(d, 0.0); out.append((d, v))
    return out


def overnight(bars: list[Bar], cost: float = 0.0009, min_hold_days: int = 1) -> list[tuple[str, float]]:
    """Compra no leilão de fechamento, vende no leilão de abertura seguinte.
    Dias de provento: o provento é recebido (usa o fator de ajuste)."""
    v = 1.0; out = [(bars[0].day, 1.0)]
    for i in range(1, len(bars)):
        prev, cur = bars[i - 1], bars[i]
        r = (cur.o * cur.adj) / (prev.c * prev.adj) - 1
        v *= 1 + r - cost; out.append((cur.day, v))
    return out


def tsmom(bars: list[Bar], cdi: dict[str, float], lookback: int = 210, cost: float = 0.0005) -> list[tuple[str, float]]:
    """Fica no ativo quando o retorno de ~10 meses supera o CDI acumulado do
    mesmo período; senão fica no CDI. Rebalanceia no 1º pregão do mês."""
    v = 1.0; out = [(bars[0].day, 1.0)]; inside = False
    adj = [b.c * b.adj for b in bars]
    for i in range(1, len(bars)):
        d = bars[i].day
        if inside:
            v *= adj[i] / adj[i - 1]
        else:
            v *= 1 + cdi.get(d, 0.0)
        if i > lookback and d[:7] != bars[i - 1].day[:7]:
            r = adj[i] / adj[i - lookback] - 1
            rf = math.prod(1 + cdi.get(bars[k].day, 0.0) for k in range(i - lookback + 1, i + 1)) - 1
            want = r > rf
            if want != inside:
                v *= 1 - cost; inside = want
        out.append((d, v))
    return out


def trend_ma(bars: list[Bar], ma: int = 100, cost: float = 0.002, cash_rate: dict[str, float] | None = None) -> list[tuple[str, float]]:
    """Comprado quando o fechamento está acima da média de `ma` dias; senão caixa."""
    v = 1.0; out = [(bars[0].day, 1.0)]; inside = False
    c = [b.c for b in bars]
    for i in range(1, len(bars)):
        if inside:
            v *= c[i] / c[i - 1]
        elif cash_rate:
            v *= 1 + cash_rate.get(bars[i].day, 0.0)
        if i >= ma:
            want = c[i] > sum(c[i - ma + 1:i + 1]) / ma
            if want != inside:
                v *= 1 - cost; inside = want
        out.append((bars[i].day, v))
    return out


def covered_call(bars: list[Bar], cdi: dict[str, float], otm: float = 0.05, vrp: float = 1.15, cost: float = 0.003) -> list[tuple[str, float]]:
    """Mensal: compra o ativo e vende call 5% fora do dinheiro com vencimento em
    ~21 pregões. Prêmio ESTIMADO por Black-Scholes (vol implícita = vol realizada
    de 21 dias x vrp). Na data do vencimento, o ganho é limitado ao strike."""
    v = 1.0; out = [(bars[0].day, 1.0)]
    adj = [b.c * b.adj for b in bars]
    i = 22
    while i + 21 < len(bars):
        rets = [math.log(adj[k] / adj[k - 1]) for k in range(i - 20, i + 1)]
        m = sum(rets) / len(rets); rv = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1)) * math.sqrt(252)
        s0 = adj[i]; k_ = s0 * (1 + otm); t = 21 / 252
        rf = sum(cdi.get(bars[j].day, 0.0) for j in range(i - 20, i + 1)) / 21 * 252
        prem = black_scholes(s0, k_, t, rf, max(rv * vrp, 0.05), "call")
        for j in range(i + 1, i + 22):
            out.append((bars[j].day, v * min(adj[j], k_) / s0 + v * prem / s0 if j == i + 21 else v * adj[j] / s0))
        s1 = adj[i + 21]
        v *= (min(s1, k_) + prem) / s0 - cost
        out[-1] = (bars[i + 21].day, v)
        i += 21
    return out


def run(out: Path = Path("data/cases/estrategias-10-anos.json")) -> dict:
    errors = []
    try:
        cdi = fetch_cdi("2014-01-01")
    except Exception as e:  # noqa: BLE001
        cdi = {}; errors.append(f"CDI: {type(e).__name__}: {str(e)[:80]}")
    if cdi:
        out.parent.mkdir(parents=True, exist_ok=True)
        (out.parent / "cdi.json").write_text(json.dumps(cdi), encoding="utf-8")
    rep = {"nota": __doc__.strip(), "erros": errors, "acoes": {}, "opcoes": {}, "bitcoin": {}}
    for t in ["BOVA11", "PETR4", "VALE3", "ITUB4", "WEGE3", "SUZB3"]:
        try:
            bars = load_yahoo_daily(t)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{t}: {e}"); continue
        days = [b.day for b in bars]
        r = {"comprar_e_segurar": _metrics(buy_hold(bars), cdi), "efeito_noite": _metrics(overnight(bars), cdi)}
        if t == "BOVA11":
            r["momentum_vs_cdi"] = _metrics(tsmom(bars, cdi), cdi)
            r["cdi"] = _metrics(cdi_curve(days, cdi), cdi)
            rep["opcoes"]["venda_coberta_BOVA11_estimada"] = _metrics(covered_call(bars, cdi), cdi)
            rep["opcoes"]["referencia_BOVA11_comprar_e_segurar"] = r["comprar_e_segurar"]
        if t == "PETR4":
            rep["opcoes"]["venda_coberta_PETR4_estimada"] = _metrics(covered_call(bars, cdi), cdi)
            rep["opcoes"]["referencia_PETR4_comprar_e_segurar"] = r["comprar_e_segurar"]
        rep["acoes"][t] = r
    try:
        btc = load_yahoo_daily("BTC-USD", "US")
        rep["bitcoin"] = {"periodo": f"{btc[0].day} a {btc[-1].day}",
                          "comprar_e_segurar": _metrics(buy_hold(btc)),
                          "tendencia_media_50": _metrics(trend_ma(btc, 50)),
                          "tendencia_media_100": _metrics(trend_ma(btc, 100)),
                          "tendencia_media_200": _metrics(trend_ma(btc, 200))}
    except Exception as e:  # noqa: BLE001
        errors.append(f"BTC: {e}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    return rep


if __name__ == "__main__":
    rep = run()
    for grp in ("acoes", "opcoes", "bitcoin"):
        print("==", grp)
        for k, v in rep[grp].items():
            print(" ", k, v)
    print("erros", rep["erros"])
