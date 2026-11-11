"""Estratégias com opções: construção de pernas, payoff no vencimento,
break-evens, lucro máximo e perda máxima.

Convenção: quantidade positiva = comprado (long), negativa = vendido (short).
Perna de ação usa strike=None.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .pricing import OptionType


@dataclass(frozen=True)
class Leg:
    kind: str                    # "call" | "put" | "stock"
    quantity: float              # + comprado, - vendido (em unidades do ativo)
    strike: float | None = None
    premium: float = 0.0         # preço pago/recebido por unidade (sempre positivo)

    def payoff(self, spot: float) -> float:
        if self.kind == "stock":
            return self.quantity * spot
        assert self.strike is not None
        if self.kind == "call":
            intrinsic = max(0.0, spot - self.strike)
        elif self.kind == "put":
            intrinsic = max(0.0, self.strike - spot)
        else:
            raise ValueError(f"kind inválido: {self.kind}")
        return self.quantity * intrinsic

    def cost(self) -> float:
        """Custo líquido de montagem (positivo = desembolso)."""
        if self.kind == "stock":
            return self.quantity * self.premium
        return self.quantity * self.premium


@dataclass
class Strategy:
    name: str
    legs: list[Leg] = field(default_factory=list)
    thesis: str = ""

    def net_cost(self) -> float:
        return sum(l.cost() for l in self.legs)

    def pnl(self, spot: float) -> float:
        return sum(l.payoff(spot) for l in self.legs) - self.net_cost()

    def pnl_curve(self, spots: Iterable[float]) -> list[tuple[float, float]]:
        return [(s, self.pnl(s)) for s in spots]

    def _grid(self) -> list[float]:
        strikes = [l.strike for l in self.legs if l.strike]
        ref = [l.premium for l in self.legs if l.kind == "stock"] or strikes or [100.0]
        lo = 0.0
        hi = max(max(strikes) if strikes else 0.0, max(ref)) * 2 + 1
        n = 4000
        pts = {lo + (hi - lo) * i / n for i in range(n + 1)}
        pts.update(strikes)  # garante avaliação exata nos strikes (vértices do payoff)
        return sorted(pts)

    def break_evens(self) -> list[float]:
        grid = self._grid()
        out: list[float] = []
        prev_s, prev_p = grid[0], self.pnl(grid[0])
        for s in grid[1:]:
            p = self.pnl(s)
            if prev_p == 0 or (prev_p < 0 < p) or (prev_p > 0 > p):
                # interpolação linear
                if p != prev_p:
                    be = prev_s + (0 - prev_p) * (s - prev_s) / (p - prev_p)
                else:
                    be = prev_s
                if not out or abs(out[-1] - be) > 1e-6:
                    out.append(round(be, 6))
            prev_s, prev_p = s, p
        return out

    def max_profit(self) -> float:
        """Lucro máximo na grade; float('inf') se ilimitado (cresce no extremo)."""
        grid = self._grid()
        vals = [self.pnl(s) for s in grid]
        if vals[-1] > vals[-2] + 1e-9 and vals[-1] > max(vals[:-1]):
            return float("inf")
        return max(vals)

    def max_loss(self) -> float:
        """Perda máxima (positiva); float('inf') se ilimitada."""
        grid = self._grid()
        vals = [self.pnl(s) for s in grid]
        if vals[-1] < vals[-2] - 1e-9 and vals[-1] < min(vals[:-1]):
            return float("inf")
        return -min(vals)

    def summary(self) -> dict:
        return {
            "estrategia": self.name,
            "custo_liquido": round(self.net_cost(), 4),
            "break_evens": self.break_evens(),
            "lucro_max": self.max_profit(),
            "perda_max": self.max_loss(),
            "tese": self.thesis,
        }


# ---- construtores -------------------------------------------------------

def covered_call(spot: float, strike: float, premium: float, qty: int = 100) -> Strategy:
    return Strategy("Venda coberta (covered call)", [
        Leg("stock", qty, None, spot), Leg("call", -qty, strike, premium),
    ], "Gerar renda sobre ação em carteira; aceita vender no strike.")


def cash_secured_put(strike: float, premium: float, qty: int = 100) -> Strategy:
    return Strategy("Put coberta por caixa (cash-secured put)", [
        Leg("put", -qty, strike, premium),
    ], "Receber prêmio para comprar a ação mais barata; precisa de caixa igual a strike*qty.")


def bull_call_spread(k_long: float, p_long: float, k_short: float, p_short: float, qty: int = 100) -> Strategy:
    return Strategy("Trava de alta com calls (bull call spread)", [
        Leg("call", qty, k_long, p_long), Leg("call", -qty, k_short, p_short),
    ], "Alta moderada, risco e lucro limitados; débito.")


def bear_put_spread(k_long: float, p_long: float, k_short: float, p_short: float, qty: int = 100) -> Strategy:
    return Strategy("Trava de baixa com puts (bear put spread)", [
        Leg("put", qty, k_long, p_long), Leg("put", -qty, k_short, p_short),
    ], "Baixa moderada; débito.")


def bull_put_spread(k_short: float, p_short: float, k_long: float, p_long: float, qty: int = 100) -> Strategy:
    return Strategy("Trava de alta com puts (bull put spread)", [
        Leg("put", -qty, k_short, p_short), Leg("put", qty, k_long, p_long),
    ], "Alta/lateral; crédito; ganha com theta.")


def bear_call_spread(k_short: float, p_short: float, k_long: float, p_long: float, qty: int = 100) -> Strategy:
    return Strategy("Trava de baixa com calls (bear call spread)", [
        Leg("call", -qty, k_short, p_short), Leg("call", qty, k_long, p_long),
    ], "Baixa/lateral; crédito; ganha com theta.")


def iron_condor(kp_long: float, pp_long: float, kp_short: float, pp_short: float,
                kc_short: float, pc_short: float, kc_long: float, pc_long: float,
                qty: int = 100) -> Strategy:
    return Strategy("Iron condor", [
        Leg("put", qty, kp_long, pp_long), Leg("put", -qty, kp_short, pp_short),
        Leg("call", -qty, kc_short, pc_short), Leg("call", qty, kc_long, pc_long),
    ], "Lateral com vol implícita alta; crédito; risco definido.")


def long_straddle(k: float, p_call: float, p_put: float, qty: int = 100) -> Strategy:
    return Strategy("Straddle comprado", [
        Leg("call", qty, k, p_call), Leg("put", qty, k, p_put),
    ], "Aposta em movimento forte (evento), direção indiferente; paga theta.")


def long_strangle(k_put: float, p_put: float, k_call: float, p_call: float, qty: int = 100) -> Strategy:
    return Strategy("Strangle comprado", [
        Leg("put", qty, k_put, p_put), Leg("call", qty, k_call, p_call),
    ], "Como straddle, mais barato, precisa de movimento maior.")


def butterfly_call(k1: float, p1: float, k2: float, p2: float, k3: float, p3: float, qty: int = 100) -> Strategy:
    return Strategy("Borboleta com calls", [
        Leg("call", qty, k1, p1), Leg("call", -2 * qty, k2, p2), Leg("call", qty, k3, p3),
    ], "Ativo termina perto do strike central; custo baixo, lucro limitado.")


def collar(spot: float, k_put: float, p_put: float, k_call: float, p_call: float, qty: int = 100) -> Strategy:
    return Strategy("Collar", [
        Leg("stock", qty, None, spot), Leg("put", qty, k_put, p_put), Leg("call", -qty, k_call, p_call),
    ], "Proteção de carteira financiada pela venda de call.")


def calendar_placeholder() -> Strategy:
    """Calendário (vencimentos diferentes) não é modelável por payoff no
    vencimento; exige precificação da perna longa remanescente. Ver docs."""
    raise NotImplementedError("use pricing.black_scholes para avaliar a perna longa remanescente")
