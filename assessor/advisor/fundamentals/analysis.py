"""Análise fundamentalista: múltiplos, qualidade, endividamento, DCF e score.

A regra aqui é simples: conhecer a empresa antes de qualquer operação.
`CompanyFinancials` é preenchido a partir de demonstrações públicas (CVM,
RI da empresa, SEC 10-K/10-Q). Nada aqui substitui a leitura do release.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class CompanyFinancials:
    ticker: str
    price: float
    shares_outstanding: float
    revenue: float
    ebit: float
    ebitda: float
    net_income: float
    equity: float                 # patrimônio líquido
    total_debt: float
    cash: float
    operating_cash_flow: float
    capex: float                  # positivo = investimento
    dividends_paid: float = 0.0   # últimos 12 meses
    revenue_growth_5y: float = 0.0  # CAGR 5 anos (0.10 = 10%)
    sector: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def market_cap(self) -> float:
        return self.price * self.shares_outstanding

    @property
    def enterprise_value(self) -> float:
        return self.market_cap + self.total_debt - self.cash

    @property
    def free_cash_flow(self) -> float:
        return self.operating_cash_flow - self.capex


def _safe_div(a: float, b: float) -> float | None:
    if b == 0 or b is None:
        return None
    return a / b


def ratios(c: CompanyFinancials) -> dict[str, float | None]:
    return {
        "P/L": _safe_div(c.market_cap, c.net_income),
        "P/VP": _safe_div(c.market_cap, c.equity),
        "EV/EBITDA": _safe_div(c.enterprise_value, c.ebitda),
        "EV/EBIT": _safe_div(c.enterprise_value, c.ebit),
        "P/FCF": _safe_div(c.market_cap, c.free_cash_flow),
        "ROE": _safe_div(c.net_income, c.equity),
        "ROIC": _safe_div(c.ebit * 0.66, c.equity + c.total_debt - c.cash),  # NOPAT aprox. 34% IR
        "margem_liquida": _safe_div(c.net_income, c.revenue),
        "margem_EBITDA": _safe_div(c.ebitda, c.revenue),
        "divida_liquida/EBITDA": _safe_div(c.total_debt - c.cash, c.ebitda),
        "dividend_yield": _safe_div(c.dividends_paid, c.market_cap),
        "payout": _safe_div(c.dividends_paid, c.net_income),
        "FCF_yield": _safe_div(c.free_cash_flow, c.market_cap),
        "earnings_yield": _safe_div(c.net_income, c.market_cap),
    }


@dataclass(frozen=True)
class FundamentalScore:
    total: int           # 0..100
    valuation: int       # 0..30
    quality: int         # 0..30
    safety: int          # 0..25
    growth: int          # 0..15
    flags: list[str]


def score_company(c: CompanyFinancials) -> FundamentalScore:
    """Score heurístico e transparente. Cada ponto tem uma regra legível.
    Use como filtro inicial, nunca como decisão final."""
    r = ratios(c)
    flags: list[str] = []

    def g(key: str) -> float | None:
        return r.get(key)

    # Valuation (30)
    val = 0
    pl = g("P/L")
    if pl is not None and pl > 0:
        val += 12 if pl < 10 else 8 if pl < 15 else 4 if pl < 25 else 0
    else:
        flags.append("lucro negativo ou nulo")
    ev = g("EV/EBITDA")
    if ev is not None and ev > 0:
        val += 10 if ev < 6 else 7 if ev < 9 else 3 if ev < 13 else 0
    fcfy = g("FCF_yield")
    if fcfy is not None:
        val += 8 if fcfy > 0.08 else 5 if fcfy > 0.05 else 2 if fcfy > 0.02 else 0
        if fcfy < 0:
            flags.append("queima caixa (FCF negativo)")

    # Qualidade (30)
    qual = 0
    roe = g("ROE")
    if roe is not None:
        qual += 12 if roe > 0.20 else 8 if roe > 0.12 else 4 if roe > 0.06 else 0
    roic = g("ROIC")
    if roic is not None:
        qual += 10 if roic > 0.15 else 6 if roic > 0.10 else 2 if roic > 0.05 else 0
    mg = g("margem_EBITDA")
    if mg is not None:
        qual += 8 if mg > 0.30 else 5 if mg > 0.18 else 2 if mg > 0.08 else 0

    # Segurança (25)
    saf = 0
    dl = g("divida_liquida/EBITDA")
    if dl is None:
        saf += 5
    elif dl <= 0:
        saf += 15
    elif dl < 1.5:
        saf += 12
    elif dl < 3:
        saf += 6
    else:
        flags.append(f"alavancagem alta: dívida líquida/EBITDA = {dl:.1f}x")
    if c.operating_cash_flow > c.net_income * 0.8:
        saf += 10
    else:
        flags.append("lucro não convertido em caixa (qualidade de lucro)")

    # Crescimento (15)
    gr = 0
    gcagr = c.revenue_growth_5y
    gr += 15 if gcagr > 0.15 else 10 if gcagr > 0.08 else 5 if gcagr > 0.03 else 0

    total = val + qual + saf + gr
    return FundamentalScore(total, val, qual, saf, gr, flags)


def dcf_value(fcf: float, growth_rates: list[float], discount_rate: float,
              terminal_growth: float, shares: float, net_debt: float = 0.0) -> float:
    """Valor justo por ação via fluxo de caixa descontado (FCFF simplificado).

    growth_rates: crescimento do FCF em cada ano explícito.
    """
    if discount_rate <= terminal_growth:
        raise ValueError("taxa de desconto deve exceder crescimento perpétuo")
    pv = 0.0
    cf = fcf
    for i, gth in enumerate(growth_rates, start=1):
        cf *= 1 + gth
        pv += cf / (1 + discount_rate) ** i
    n = len(growth_rates)
    terminal = cf * (1 + terminal_growth) / (discount_rate - terminal_growth)
    pv += terminal / (1 + discount_rate) ** n
    equity_value = pv - net_debt
    return equity_value / shares


def graham_number(eps: float, book_value_per_share: float) -> float | None:
    """Número de Graham: sqrt(22.5 * LPA * VPA). Só faz sentido com ambos > 0."""
    if eps <= 0 or book_value_per_share <= 0:
        return None
    return math.sqrt(22.5 * eps * book_value_per_share)
