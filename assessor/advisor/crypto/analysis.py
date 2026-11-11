"""Criptoativos: métricas de mercado/on-chain, flags de risco e sinal de funding.

Cripto opera 24/7, o que atende o objetivo de operar em todos os horários,
mas a volatilidade é 3-5x a de ações: o orçamento de risco deve ser o mesmo
em dinheiro, logo as posições são proporcionalmente menores.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from ..risk.metrics import annualized_volatility, max_drawdown


@dataclass
class CryptoAsset:
    symbol: str
    price: float
    market_cap: float
    volume_24h: float
    circulating_supply: float
    max_supply: float | None = None
    fdv: float | None = None                   # fully diluted valuation
    exchange_netflow_7d: float = 0.0           # + entrando em corretoras (pressão vendedora)
    funding_rate_8h: float = 0.0               # perpétuos; 0.0001 = 0.01%
    open_interest: float = 0.0
    daily_returns: list[float] = field(default_factory=list)
    price_history: list[float] = field(default_factory=list)
    audited: bool = False
    years_live: float = 0.0
    notes: list[str] = field(default_factory=list)


def crypto_metrics(a: CryptoAsset) -> dict[str, float | None]:
    fdv = a.fdv if a.fdv is not None else (a.price * a.max_supply if a.max_supply else None)
    return {
        "vol_anual": annualized_volatility(a.daily_returns, 365) if len(a.daily_returns) > 2 else None,
        "max_drawdown": max_drawdown(a.price_history) if a.price_history else None,
        "volume/mcap": a.volume_24h / a.market_cap if a.market_cap else None,
        "mcap/FDV": a.market_cap / fdv if fdv else None,
        "funding_anualizado": a.funding_rate_8h * 3 * 365,
        "OI/mcap": a.open_interest / a.market_cap if a.market_cap else None,
    }


def crypto_risk_flags(a: CryptoAsset) -> list[str]:
    m = crypto_metrics(a)
    flags: list[str] = []
    if m["mcap/FDV"] is not None and m["mcap/FDV"] < 0.4:
        flags.append("grande desbloqueio futuro de tokens (mcap/FDV baixo)")
    if m["volume/mcap"] is not None and m["volume/mcap"] < 0.01:
        flags.append("liquidez baixa para o tamanho")
    if m["volume/mcap"] is not None and m["volume/mcap"] > 1.0:
        flags.append("volume anormal vs. mcap: possível manipulação/wash trading")
    if a.exchange_netflow_7d > 0 and a.market_cap and a.exchange_netflow_7d * a.price / a.market_cap > 0.01:
        flags.append("entrada líquida relevante em corretoras: pressão vendedora")
    if abs(m["funding_anualizado"]) > 0.30:
        flags.append("funding extremo: posicionamento lotado, risco de squeeze")
    if not a.audited and a.symbol.upper() not in ("BTC", "ETH"):
        flags.append("contrato/protocolo sem auditoria conhecida")
    if a.years_live < 1:
        flags.append("ativo com menos de 1 ano: risco de projeto")
    return flags


def funding_signal(funding_history_8h: Sequence[float], z_threshold: float = 2.0) -> str:
    """Contrarian: funding muito acima da média => comprados lotados (viés de
    baixa); muito abaixo => vendidos lotados (viés de alta). Caso contrário neutro."""
    n = len(funding_history_8h)
    if n < 10:
        return "neutro"
    mean = sum(funding_history_8h) / n
    var = sum((x - mean) ** 2 for x in funding_history_8h) / (n - 1)
    sd = var ** 0.5
    if sd == 0:
        return "neutro"
    z = (funding_history_8h[-1] - mean) / sd
    if z > z_threshold:
        return "viés_baixa"
    if z < -z_threshold:
        return "viés_alta"
    return "neutro"
