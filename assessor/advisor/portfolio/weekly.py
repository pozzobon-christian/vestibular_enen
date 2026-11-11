"""Ciclo semanal: opera de segunda a sexta, fecha e retira lucro no fim de semana.

Regras acordadas:
- Lucro realizado na semana acima do colchão é RETIRADO (não reinvestido).
- Perda semanal acima do limite => pausa obrigatória na semana seguinte,
  com revisão escrita antes de voltar.
- Cripto opera no fim de semana apenas com o lucro retido, nunca com principal.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ..risk.sizing import RiskBudget


@dataclass(frozen=True)
class WeeklyReport:
    week_start: date
    week_end: date
    start_equity: float
    end_equity: float
    realized_pnl: float
    withdraw: float
    retain: float
    next_week_capital: float
    halted: bool
    notes: list[str]


class WeeklyCycle:
    def __init__(self, budget: RiskBudget, withdraw_fraction: float = 0.70,
                 min_withdraw: float = 0.0):
        if not 0 <= withdraw_fraction <= 1:
            raise ValueError("withdraw_fraction em [0,1]")
        self.budget = budget
        self.withdraw_fraction = withdraw_fraction
        self.min_withdraw = min_withdraw

    @staticmethod
    def week_bounds(d: date) -> tuple[date, date]:
        start = d - timedelta(days=d.weekday())
        return start, start + timedelta(days=4)

    def close_week(self, day: date, start_equity: float, end_equity: float) -> WeeklyReport:
        ws, we = self.week_bounds(day)
        pnl = end_equity - start_equity
        notes: list[str] = []
        halted = False
        withdraw = retain = 0.0
        if pnl > 0:
            withdraw = pnl * self.withdraw_fraction
            if withdraw < self.min_withdraw:
                notes.append("lucro abaixo do mínimo de retirada: tudo retido")
                withdraw = 0.0
            retain = pnl - withdraw
            notes.append(f"lucro retirado: {withdraw:.2f}; retido para alavancagem: {retain:.2f}")
        else:
            loss_pct = -pnl / start_equity if start_equity else 0.0
            if loss_pct >= self.budget.max_risk_per_week:
                halted = True
                notes.append(
                    f"perda semanal {loss_pct:.1%} >= limite {self.budget.max_risk_per_week:.1%}: "
                    "PAUSA na próxima semana e revisão escrita obrigatória")
            else:
                notes.append(f"perda semanal {loss_pct:.1%} dentro do limite")
        return WeeklyReport(ws, we, start_equity, end_equity, pnl, withdraw, retain,
                            end_equity - withdraw, halted, notes)
