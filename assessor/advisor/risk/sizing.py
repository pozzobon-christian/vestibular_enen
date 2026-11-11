"""Dimensionamento de posição e margem de erro.

Toda operação parte de um RiskBudget acordado: quanto do capital pode ser
perdido por operação, por dia e por semana. O sistema recusa qualquer ordem
que ultrapasse o orçamento. Isso é a "margem de erro calculada e acordada".
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RiskBudget:
    """Orçamento de risco acordado com o investidor (frações do capital)."""

    capital: float
    max_risk_per_trade: float = 0.01   # 1% do capital por operação
    max_risk_per_day: float = 0.03     # 3% por dia
    max_risk_per_week: float = 0.06    # 6% por semana: para e revisa
    max_position_pct: float = 0.20     # nenhuma posição > 20% do capital
    max_correlated_pct: float = 0.40   # setor/tema correlacionado <= 40%

    def __post_init__(self) -> None:
        if self.capital <= 0:
            raise ValueError("capital deve ser positivo")
        for name in ("max_risk_per_trade", "max_risk_per_day", "max_risk_per_week",
                     "max_position_pct", "max_correlated_pct"):
            v = getattr(self, name)
            if not 0 < v <= 1:
                raise ValueError(f"{name} deve estar em (0, 1]")
        if not self.max_risk_per_trade <= self.max_risk_per_day <= self.max_risk_per_week:
            raise ValueError("limites devem ser crescentes: trade <= dia <= semana")

    @property
    def risk_per_trade_amount(self) -> float:
        return self.capital * self.max_risk_per_trade


@dataclass(frozen=True)
class PositionSize:
    quantity: float
    notional: float
    risk_amount: float
    risk_per_unit: float
    capped_by: str = field(default="risco")  # "risco" | "posicao_max" | "caixa"


def position_size(
    budget: RiskBudget,
    entry: float,
    stop: float,
    lot: int = 1,
    cash_available: float | None = None,
    risk_fraction: float | None = None,
) -> PositionSize:
    """Calcula a quantidade a operar a partir do stop.

    quantidade = risco_permitido / |entrada - stop|, limitada pelo tamanho
    máximo de posição e pelo caixa disponível. Sempre arredonda para baixo
    em múltiplos do lote.
    """
    if entry <= 0 or stop <= 0:
        raise ValueError("preços devem ser positivos")
    risk_per_unit = abs(entry - stop)
    if risk_per_unit == 0:
        raise ValueError("stop não pode ser igual à entrada")
    frac = budget.max_risk_per_trade if risk_fraction is None else risk_fraction
    if frac > budget.max_risk_per_trade:
        raise ValueError("risco pedido excede o orçamento acordado por operação")
    risk_amount = budget.capital * frac

    qty_by_risk = risk_amount / risk_per_unit
    qty_by_position = budget.capital * budget.max_position_pct / entry
    cash = budget.capital if cash_available is None else cash_available
    qty_by_cash = cash / entry

    qty, capped = min(
        (qty_by_risk, "risco"), (qty_by_position, "posicao_max"), (qty_by_cash, "caixa"),
        key=lambda t: t[0],
    )
    qty = (int(qty) // lot) * lot
    return PositionSize(
        quantity=qty,
        notional=qty * entry,
        risk_amount=qty * risk_per_unit,
        risk_per_unit=risk_per_unit,
        capped_by=capped,
    )


def kelly_fraction(win_rate: float, payoff_ratio: float, fraction: float = 0.5) -> float:
    """Critério de Kelly (fracionado).

    f* = p - (1-p)/b, onde b = ganho médio / perda média.
    Usamos meio-Kelly por padrão: Kelly cheio é agressivo demais para a
    incerteza real das estimativas. Nunca retorna negativo (sem edge => 0).
    """
    if not 0 <= win_rate <= 1:
        raise ValueError("win_rate em [0,1]")
    if payoff_ratio <= 0:
        raise ValueError("payoff_ratio > 0")
    f = win_rate - (1 - win_rate) / payoff_ratio
    return max(0.0, f * fraction)


def risk_of_ruin(win_rate: float, risk_per_trade: float, ruin_level: float = 0.5,
                 payoff_ratio: float = 1.0) -> float:
    """Probabilidade aproximada de perder `ruin_level` do capital.

    Aproximação clássica para apostas com razão de payoff b:
    RoR = ((1 - edge) / (1 + edge)) ** (ruin_level / risk_per_trade),
    com edge = p*b - (1-p) normalizado por b. Serve para comparar cenários,
    não como previsão exata.
    """
    if risk_per_trade <= 0:
        raise ValueError("risk_per_trade > 0")
    edge = (win_rate * payoff_ratio - (1 - win_rate)) / payoff_ratio
    if edge <= 0:
        return 1.0
    units = ruin_level / risk_per_trade
    return ((1 - edge) / (1 + edge)) ** units
