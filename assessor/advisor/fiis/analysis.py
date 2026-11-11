"""Fundos imobiliários (FIIs) e REITs: métricas e score.

Fontes: relatórios gerenciais mensais, informes CVM, site do administrador.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FII:
    ticker: str
    price: float
    book_value_per_share: float          # VP por cota
    dividends_12m: float                 # soma dos rendimentos por cota em 12m
    last_dividend: float
    segment: str                         # "tijolo-logistica", "tijolo-lajes", "papel", "shopping", "fof", "hibrido"
    vacancy_physical: float = 0.0        # 0.05 = 5%
    vacancy_financial: float = 0.0
    num_properties: int = 0
    num_tenants: int = 0
    top_tenant_share: float = 0.0        # concentração do maior inquilino na receita
    avg_lease_years: float = 0.0         # prazo médio remanescente dos contratos
    leverage: float = 0.0                # dívida / ativos
    liquidity_daily_brl: float = 0.0     # volume médio diário
    management_fee: float = 0.0          # taxa ADM+gestão a.a.
    cap_rate: float | None = None        # para tijolo: NOI / valor dos imóveis
    cdi_or_rf_ref: float = 0.10          # referência de taxa livre de risco (CDI ou Treasury)
    notes: list[str] = field(default_factory=list)


def fii_metrics(f: FII) -> dict[str, float]:
    dy = f.dividends_12m / f.price if f.price else 0.0
    return {
        "P/VP": f.price / f.book_value_per_share if f.book_value_per_share else 0.0,
        "DY_12m": dy,
        "DY_mensal_anualizado": f.last_dividend * 12 / f.price if f.price else 0.0,
        "spread_vs_rf": dy - f.cdi_or_rf_ref,
        "vacancia_fisica": f.vacancy_physical,
        "vacancia_financeira": f.vacancy_financial,
        "concentracao_maior_inquilino": f.top_tenant_share,
        "alavancagem": f.leverage,
    }


def fii_score(f: FII) -> tuple[int, list[str]]:
    """Score 0..100 com regras explícitas. Retorna (score, alertas)."""
    m = fii_metrics(f)
    s = 0
    flags: list[str] = []

    pvp = m["P/VP"]
    if 0 < pvp < 0.85:
        s += 20; flags.append("desconto grande sobre VP: verificar motivo")
    elif pvp < 0.95:
        s += 18
    elif pvp <= 1.05:
        s += 12
    elif pvp <= 1.2:
        s += 5
    else:
        flags.append("ágio alto sobre VP")

    spread = m["spread_vs_rf"]
    s += 20 if spread > 0.03 else 14 if spread > 0.01 else 6 if spread > -0.01 else 0
    if spread < -0.01:
        flags.append("DY abaixo da renda fixa: exige tese de ganho de capital")

    vac = max(f.vacancy_physical, f.vacancy_financial)
    s += 15 if vac < 0.05 else 10 if vac < 0.12 else 3 if vac < 0.25 else 0
    if vac >= 0.25:
        flags.append("vacância elevada")

    if f.segment in ("papel", "fof"):
        s += 10  # diversificação intrínseca; concentração tratada no gestor
    else:
        s += 10 if f.top_tenant_share < 0.20 else 6 if f.top_tenant_share < 0.40 else 0
        if f.top_tenant_share >= 0.40:
            flags.append("dependência de um inquilino")
        s += 5 if f.num_properties >= 8 else 2 if f.num_properties >= 3 else 0

    s += 10 if f.leverage < 0.10 else 6 if f.leverage < 0.25 else 0
    if f.leverage >= 0.25:
        flags.append("alavancagem relevante para um FII")

    s += 10 if f.liquidity_daily_brl >= 2_000_000 else 6 if f.liquidity_daily_brl >= 500_000 else 1
    if f.liquidity_daily_brl < 500_000:
        flags.append("baixa liquidez: cuidado com spreads e saída")

    s += 5 if f.management_fee <= 0.01 else 2 if f.management_fee <= 0.015 else 0
    if f.segment.startswith("tijolo") and f.avg_lease_years and f.avg_lease_years < 2:
        flags.append("contratos curtos: risco de renegociação")
    return min(100, s), flags
