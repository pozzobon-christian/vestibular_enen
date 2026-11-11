"""Interface de corretora. A execução real é plugada pelo usuário com as
próprias credenciais (ex.: Interactive Brokers, Binance, corretora BR com API).

PaperBroker simula execução para validar o sistema antes de qualquer real.
Toda ordem passa pelo RiskGate antes de chegar à corretora.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..risk.sizing import RiskBudget
from ..risk.leverage import LeveragePolicy


@dataclass(frozen=True)
class Order:
    ticker: str
    market: str
    side: str                 # buy | sell
    quantity: float
    price: float              # limite ou referência
    stop: float | None
    thesis: str
    order_type: str = "limit"


@dataclass(frozen=True)
class OrderResult:
    accepted: bool
    filled_qty: float
    fill_price: float
    reason: str


class Broker(ABC):
    @abstractmethod
    def place(self, order: Order) -> OrderResult: ...

    @abstractmethod
    def equity(self) -> float: ...


@dataclass
class RiskGate:
    """Porteiro: recusa ordens fora do orçamento e sem stop/tese."""
    budget: RiskBudget
    leverage: LeveragePolicy
    day_loss: float = 0.0
    week_loss: float = 0.0
    open_notional: float = 0.0
    rejections: list[str] = field(default_factory=list)

    def check(self, order: Order, equity: float) -> tuple[bool, str]:
        if not order.thesis.strip():
            return self._reject("ordem sem tese")
        if order.side == "buy" and order.stop is None:
            return self._reject("compra sem stop definido")
        if order.stop is not None:
            risk = abs(order.price - order.stop) * order.quantity
            if risk > self.budget.risk_per_trade_amount + 1e-9:
                return self._reject(f"risco {risk:.2f} > limite por operação {self.budget.risk_per_trade_amount:.2f}")
            if self.day_loss + risk > self.budget.capital * self.budget.max_risk_per_day:
                return self._reject("limite de perda diária seria ultrapassado")
            if self.week_loss + risk > self.budget.capital * self.budget.max_risk_per_week:
                return self._reject("limite de perda semanal seria ultrapassado")
        notional = order.price * order.quantity
        if notional > self.budget.capital * self.budget.max_position_pct + 1e-9:
            return self._reject("posição excede o tamanho máximo acordado")
        if order.side == "buy":
            lev = self.leverage.evaluate(equity, self.open_notional + notional)
            if not lev.allowed:
                return self._reject(lev.reason)
        return True, "ok"

    def _reject(self, why: str) -> tuple[bool, str]:
        self.rejections.append(why)
        return False, why


class PaperBroker(Broker):
    def __init__(self, cash: float, gate: RiskGate, slippage_bps: float = 5.0, fee_bps: float = 3.0):
        self.cash = cash
        self.gate = gate
        self.slippage = slippage_bps / 10_000
        self.fee = fee_bps / 10_000
        self.positions: dict[str, tuple[float, float]] = {}  # ticker -> (qty, avg)
        self.marks: dict[str, float] = {}

    def mark(self, ticker: str, price: float) -> None:
        self.marks[ticker] = price

    def equity(self) -> float:
        val = self.cash
        for t, (q, avg) in self.positions.items():
            val += q * self.marks.get(t, avg)
        return val

    def place(self, order: Order) -> OrderResult:
        ok, reason = self.gate.check(order, self.equity())
        if not ok:
            return OrderResult(False, 0.0, 0.0, reason)
        sign = 1 if order.side == "buy" else -1
        fill = order.price * (1 + sign * self.slippage)
        cost = fill * order.quantity
        fees = cost * self.fee
        if order.side == "buy" and cost + fees > self.cash:
            return OrderResult(False, 0.0, 0.0, "caixa insuficiente")
        q, avg = self.positions.get(order.ticker, (0.0, 0.0))
        if order.side == "buy":
            new_q = q + order.quantity
            avg = (q * avg + cost) / new_q
            self.cash -= cost + fees
            self.positions[order.ticker] = (new_q, avg)
            self.gate.open_notional += cost
        else:
            if order.quantity > q:
                return OrderResult(False, 0.0, 0.0, "venda maior que posição (short não habilitado no paper)")
            self.cash += cost - fees
            new_q = q - order.quantity
            self.positions[order.ticker] = (new_q, avg if new_q else 0.0)
            self.gate.open_notional = max(0.0, self.gate.open_notional - order.quantity * avg)
        self.mark(order.ticker, fill)
        return OrderResult(True, order.quantity, fill, "executada (paper)")
