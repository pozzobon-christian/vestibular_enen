"""Balanços públicos: preenche CompanyFinancials a partir do Yahoo Finance
(quoteSummary: demonstrações e estatísticas, originadas de CVM/SEC). Sem chave.
A fonte primária continua sendo CVM/RI/SEC; isto é o atalho diário."""
from __future__ import annotations

import time

from .market import yahoo_symbol, yahoo_quote_summary
from ..fundamentals.analysis import CompanyFinancials

MODULES = "financialData,defaultKeyStatistics,incomeStatementHistory,balanceSheetHistory,cashflowStatementHistory,price,summaryProfile"


def _num(d, *keys, default=0.0):
    for k in keys:
        v = d.get(k) if isinstance(d, dict) else None
        if isinstance(v, dict):
            v = v.get("raw")
        if v is not None:
            return float(v)
    return default


def fetch_company(ticker: str, market: str = "BR", timeout: int = 20) -> CompanyFinancials:
    sym = yahoo_symbol(ticker, market)
    d = yahoo_quote_summary(sym, MODULES, timeout)
    fin, ks, price = d.get("financialData", {}), d.get("defaultKeyStatistics", {}), d.get("price", {})
    inc = (d.get("incomeStatementHistory", {}).get("incomeStatementHistory") or [{}])[0]
    bs = (d.get("balanceSheetHistory", {}).get("balanceSheetStatements") or [{}])[0]
    cf = (d.get("cashflowStatementHistory", {}).get("cashflowStatements") or [{}])[0]
    px = _num(price, "regularMarketPrice") or _num(fin, "currentPrice")
    shares = _num(ks, "sharesOutstanding")
    revenue = _num(fin, "totalRevenue") or _num(inc, "totalRevenue")
    ebitda = _num(fin, "ebitda")
    ebit = _num(inc, "ebit") or _num(inc, "operatingIncome") or ebitda * 0.8
    net = _num(inc, "netIncome") or (_num(ks, "trailingEps") * shares if shares else 0.0)
    equity = _num(bs, "totalStockholderEquity") or (px * shares / _num(ks, "priceToBook", default=1.0) if shares else 0.0)
    debt = _num(fin, "totalDebt") or _num(bs, "longTermDebt") + _num(bs, "shortLongTermDebt")
    cash = _num(fin, "totalCash") or _num(bs, "cash")
    ocf = _num(fin, "operatingCashflow") or _num(cf, "totalCashFromOperatingActivities")
    capex = abs(_num(cf, "capitalExpenditures"))
    divs = abs(_num(cf, "dividendsPaid"))
    growth = _num(fin, "revenueGrowth")
    return CompanyFinancials(
        ticker=ticker, price=px, shares_outstanding=shares, revenue=revenue, ebit=ebit, ebitda=ebitda,
        net_income=net, equity=equity, total_debt=debt, cash=cash, operating_cash_flow=ocf, capex=capex,
        dividends_paid=divs, revenue_growth_5y=growth, sector=(d.get("summaryProfile") or {}).get("sector", ""),
        notes=[f"fonte: Yahoo quoteSummary ({sym}); crescimento é o último ano, não CAGR 5 anos"],
    )


def fetch_many(tickers: list[str], market: str, errors: list[str], sleep: float = 0.6) -> dict[str, CompanyFinancials]:
    out = {}
    for t in tickers:
        try:
            out[t] = fetch_company(t, market)
        except Exception as e:  # noqa: BLE001
            errors.append(f"balanco {t}: {type(e).__name__}: {str(e)[:100]}")
        time.sleep(sleep)
    return out
