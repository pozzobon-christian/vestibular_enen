"""Política de alavancagem: só se alavanca lucro, nunca capital principal."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeverageDecision:
    allowed: bool
    max_leveraged_notional: float
    reason: str


@dataclass(frozen=True)
class LeveragePolicy:
    """Regra acordada: a base alavancável é apenas o lucro acumulado ainda não
    retirado. O capital principal opera sempre 1:1.

    max_multiplier: quantas vezes o lucro retido pode ser alavancado.
    profit_buffer: fração do lucro que fica intocada como colchão.
    """

    principal: float
    max_multiplier: float = 2.0
    profit_buffer: float = 0.30

    def __post_init__(self) -> None:
        if self.principal <= 0:
            raise ValueError("principal > 0")
        if self.max_multiplier < 1:
            raise ValueError("max_multiplier >= 1")
        if not 0 <= self.profit_buffer < 1:
            raise ValueError("profit_buffer em [0,1)")

    def evaluate(self, equity: float, requested_notional: float) -> LeverageDecision:
        retained_profit = max(0.0, equity - self.principal)
        leverable = retained_profit * (1 - self.profit_buffer)
        limit = self.principal + leverable * self.max_multiplier
        if retained_profit <= 0:
            return LeverageDecision(
                allowed=requested_notional <= self.principal,
                max_leveraged_notional=self.principal,
                reason="sem lucro retido: operar somente 1:1 sobre o principal",
            )
        if requested_notional <= limit:
            return LeverageDecision(True, limit, "dentro do limite de alavancagem sobre lucro")
        return LeverageDecision(False, limit, f"excede limite: notional máximo {limit:.2f}")
