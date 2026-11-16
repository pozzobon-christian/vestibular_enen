"""Porteiro de tese: nenhuma ordem, nem as escritas à mão no plano, passa sem
a votação das camadas. Nasceu do erro de 11/11 (compra de BTC contra a
tendência, sem estabilização, com análogos de amostra insuficiente).

Regras (todas verificáveis nos dados):
1. Contra a tendência (score de baixa >= 50 para compra, ou de alta para venda)
   só com ESTABILIZAÇÃO: fechamento acima da máxima dos 3 dias anteriores e
   acima da média de 5 dias (ou o espelho para venda). RSI baixo não é sinal.
2. Análogos só contam com n >= 8. Abaixo disso são "sem evidência".
3. Cripto: compra bloqueada se o composto de risco cripto estiver negativo
   (2 de 3: IBIT caindo em 5 dias, COIN/MSTR em tendência de baixa, BTC abaixo
   da mínima de 20 dias) e sem estabilização.
4. Regime defensivo: compra só em ativo com tendência própria de alta
   (score >= 50) ou com estabilização; nunca "porque caiu muito".
5. Duas camadas a favor e nenhuma contra (a regra geral) continua valendo.
6. Stop em estrutura: para compra, abaixo da mínima recente (5 dias) ou 1 ATR,
   o que for mais largo dentro do orçamento; nunca um percentual arbitrário.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class GateResult:
    approved: bool
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    stabilization: bool | None = None
    structural_stop: float | None = None

    def as_dict(self) -> dict:
        return {"aprovada": self.approved, "motivos": self.reasons, "bloqueios": self.blockers,
                "estabilizacao": self.stabilization, "stop_estrutural": self.structural_stop}


def stabilization(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], side: str = "compra") -> bool:
    """Compra: fechamento acima da máxima dos 3 dias anteriores E acima da média de 5.
    Venda: espelho."""
    if len(closes) < 6:
        return False
    ema5 = sum(closes[-5:]) / 5
    if side == "compra":
        return closes[-1] > max(highs[-4:-1]) and closes[-1] > ema5
    return closes[-1] < min(lows[-4:-1]) and closes[-1] < ema5


def structural_stop(lows: Sequence[float], highs: Sequence[float], closes: Sequence[float], atr_value: float, side: str = "compra") -> float:
    """Compra: o menor entre (mínima de 5 dias) e (fechamento − 1 ATR). Venda: espelho."""
    if side == "compra":
        return round(min(min(lows[-5:]), closes[-1] - atr_value), 4)
    return round(max(max(highs[-5:]), closes[-1] + atr_value), 4)


def crypto_risk_composite(ibit_5d: float | None, coin_trend: str | None, mstr_trend: str | None,
                          btc_close: float, btc_low20: float) -> dict:
    """Negativo quando 2 de 3 flags estão acesas."""
    flags = {
        "ibit_saindo": ibit_5d is not None and ibit_5d < -0.03,
        "proxies_em_baixa": (coin_trend == "baixa") or (mstr_trend == "baixa"),
        "btc_abaixo_min20": btc_close <= btc_low20 * 1.005,
    }
    n = sum(1 for v in flags.values() if v)
    return {"flags": flags, "negativo": n >= 2, "n": n}


def order_gate(side: str, votes: dict, trend_direction: str, trend_score: int, regime_mode: str,
               stab: bool, analog_n: int | None, crypto_risk: dict | None = None,
               risk_brl: float | None = None, risk_limit_brl: float | None = None) -> GateResult:
    g = GateResult(approved=True, stabilization=stab)
    fav = sum(1 for v in votes.values() if v == "a_favor")
    con = sum(1 for v in votes.values() if v == "contra")
    want = "compra" if side == "buy" or side == "compra" else "venda"
    # 1. contra a tendência
    against = (want == "compra" and trend_direction == "baixa" and trend_score >= 50) or \
              (want == "venda" and trend_direction == "alta" and trend_score >= 50)
    if against and not stab:
        g.blockers.append(f"contra a tendência ({trend_direction} {trend_score}) sem estabilização")
    elif against and stab:
        g.reasons.append("contra a tendência, mas com estabilização confirmada: tamanho reduzido à metade")
    # 2. análogos
    if analog_n is not None and analog_n < 8:
        g.reasons.append(f"análogos com n={analog_n} < 8: não contam como evidência")
        votes = {k: ("neutro" if k == "analogos" else v) for k, v in votes.items()}
        fav = sum(1 for v in votes.values() if v == "a_favor"); con = sum(1 for v in votes.values() if v == "contra")
    # 3. cripto
    if crypto_risk and want == "compra" and crypto_risk.get("negativo") and not stab:
        on = [k for k, v in crypto_risk["flags"].items() if v]
        g.blockers.append(f"composto de risco cripto negativo ({', '.join(on)}) sem estabilização")
    # 4. regime
    if regime_mode == "defensivo" and want == "compra" and not (trend_direction == "alta" and trend_score >= 50) and not stab:
        g.blockers.append("regime defensivo: compra só com tendência própria de alta ou estabilização")
    # 5. votação
    if want == "compra" and not (fav >= 2 and con == 0):
        g.blockers.append(f"votação insuficiente: {fav} a favor, {con} contra (precisa 2+ a favor e 0 contra)")
    if want == "venda" and not (con >= 2 and fav == 0):
        g.blockers.append(f"votação insuficiente para venda: {con} contra, {fav} a favor")
    # 6. risco
    if risk_brl is not None and risk_limit_brl is not None and risk_brl > risk_limit_brl + 1e-9:
        g.blockers.append(f"risco R$ {risk_brl:.2f} acima do limite R$ {risk_limit_brl:.2f}")
    g.approved = not g.blockers
    if g.approved:
        g.reasons.append(f"votação {fav} a favor, {con} contra; tendência {trend_direction} {trend_score}; regime {regime_mode}")
    return g
