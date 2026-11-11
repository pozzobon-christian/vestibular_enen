"""Sinal de boiada.

A boiada tem três fases, e cada uma pede uma ação diferente:

1. INICIO  (poucos autores, líderes conhecidos, alcance ainda baixo):
   entrar a favor com stop curto. É aqui que o movimento tem assimetria.
2. LOTADA  (muitos autores, alcance alto, pico de menções, seguidores de
   baixo histórico chegando): não entrar; se está dentro, realizar parcial
   e subir o stop. O último a entrar é quem paga a conta.
3. REVERSAO (menções caindo, preço perde a máxima do pico, líderes sumiram
   ou viraram): contra o movimento com risco definido (put/trava), ou só
   ficar de fora.

Tudo passa pelo RiskBudget: o tamanho vem do stop, nunca da empolgação.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .network import Campaign


@dataclass(frozen=True)
class HerdSignal:
    ticker: str
    direction: str            # compra | venda (direção da boiada)
    phase: str                # inicio | lotada | reversao | ignorar
    action: str               # texto operacional
    confidence: float         # 0..1
    reasons: list[str]
    stop_hint: str            # como colocar o stop


def herd_signal(campaign: Campaign, author_stats: dict[str, dict], now: datetime | None = None,
                price_vs_peak: float | None = None, mentions_trend: float | None = None,
                early_authors: int = 4, crowded_authors: int = 8, crowded_reach: int = 200_000) -> HerdSignal:
    """
    price_vs_peak: preço atual / máxima desde o início da campanha (ex.: 0,93 = 7% abaixo).
    mentions_trend: menções nas últimas 6h / menções nas 6h anteriores (< 0,6 = esvaziando).
    """
    now = now or campaign.end
    reasons: list[str] = []
    age_h = (now - campaign.start).total_seconds() / 3600

    # qualidade de quem está na campanha
    leader_stats = author_stats.get(campaign.leader, {})
    leader_hit = leader_stats.get("acerto_5d")
    pumpers = [a for a in campaign.authors if author_stats.get(a, {}).get("assinatura_pump", 0) > 0.5]
    good = [a for a in campaign.authors if (author_stats.get(a, {}).get("acerto_5d") or 0) >= 0.55
            and author_stats.get(a, {}).get("chamadas", 0) >= 10]
    if pumpers:
        reasons.append(f"{len(pumpers)} autor(es) com assinatura de pump-and-dump: {', '.join(pumpers[:3])}")
    if good:
        reasons.append(f"{len(good)} autor(es) com histórico de acerto >= 55%: {', '.join(good[:3])}")
    if leader_hit is not None:
        reasons.append(f"líder {campaign.leader} acerta {leader_hit:.0%} em 5 dias")

    confidence = 0.3
    confidence += 0.1 * min(len(good), 3)
    confidence -= 0.15 * min(len(pumpers), 3)

    # reversão
    if (price_vs_peak is not None and price_vs_peak < 0.93) or (mentions_trend is not None and mentions_trend < 0.6):
        reasons.append("preço perdeu a máxima do pico ou menções esvaziando")
        if pumpers:
            reasons.append("campanha liderada por pumpers: reversão tende a ser completa")
            confidence += 0.2
        opposite = "venda" if campaign.direction_is_buy() else "compra"
        return HerdSignal(campaign.ticker, campaign.stance, "reversao",
                          f"contra a boiada ({opposite}) com risco definido: put/trava, ou ficar fora",
                          min(0.9, max(0.1, confidence)), reasons,
                          "stop acima da máxima do pico (ou abaixo da mínima, se campanha de venda)")

    # lotada
    if campaign.n_authors >= crowded_authors or campaign.reach >= crowded_reach or age_h > 48:
        reasons.append(f"{campaign.n_authors} autores, alcance {campaign.reach}, {age_h:.0f}h de campanha")
        return HerdSignal(campaign.ticker, campaign.stance, "lotada",
                          "não entrar; se posicionado, realizar 50% e subir o stop para o custo",
                          min(0.9, max(0.1, confidence)), reasons, "stop no custo; alvo o restante no pico de menções")

    # início
    if campaign.n_authors <= early_authors and not pumpers:
        reasons.append("campanha jovem, poucos autores, sem pumpers conhecidos")
        return HerdSignal(campaign.ticker, campaign.stance, "inicio",
                          f"entrar a favor ({campaign.stance}) com tamanho pelo RiskBudget",
                          min(0.9, max(0.1, confidence + 0.1)), reasons,
                          "stop na mínima do candle do primeiro post (ou máxima, se venda); nunca mais que 1x ATR")
    if campaign.n_authors <= early_authors and pumpers:
        reasons.append("início de campanha de pumpers: entrar só com alvo em horas, nunca carregar")
        return HerdSignal(campaign.ticker, campaign.stance, "inicio",
                          "scalp a favor com alvo curto e stop curto, ou ignorar",
                          min(0.6, max(0.1, confidence)), reasons, "stop 1x ATR; saída no primeiro sinal de lotação")
    reasons.append("fase intermediária sem assimetria clara")
    return HerdSignal(campaign.ticker, campaign.stance, "ignorar", "observar; sem ordem",
                      min(0.9, max(0.1, confidence)), reasons, "n/a")

