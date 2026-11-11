"""Rede de co-menção e detecção de campanhas coordenadas.

Dois influenciadores ficam ligados quando mencionam o mesmo ativo, na mesma
direção, dentro de uma janela curta. Repetido ao longo do tempo, isso revela
grupos que "apostam juntos", independentemente do que declaram.

Uma Campanha é: N autores distintos, mesmo ativo, mesma direção, dentro de
`window_hours`. Registra quem postou primeiro (líderes) e quem veio depois
(seguidores), e o alcance total. É a matéria-prima do sinal de boiada.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import combinations

from .posts import Post


@dataclass
class Campaign:
    ticker: str
    stance: str
    start: datetime
    end: datetime
    authors: list[str]                 # em ordem de primeiro post
    posts: list[Post]
    reach: int                         # soma de engajamento
    leader: str                        # primeiro a postar
    lag_minutes: list[float] = field(default_factory=list)  # atraso de cada autor vs. líder

    @property
    def n_authors(self) -> int:
        return len(self.authors)

    def direction_is_buy(self) -> bool:
        return self.stance == "compra"

    @property
    def duration_hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600

    def summary(self) -> dict:
        return {
            "ativo": self.ticker, "direcao": self.stance, "inicio": self.start.isoformat(),
            "autores": self.n_authors, "lider": self.leader, "duracao_h": round(self.duration_hours, 2),
            "alcance": self.reach, "posts": len(self.posts),
            "seguidores_em_ordem": self.authors[1:],
        }


def detect_campaigns(posts: list[Post], window_hours: float = 24.0, min_authors: int = 3) -> list[Campaign]:
    by_key: dict[tuple[str, str], list[Post]] = defaultdict(list)
    for p in posts:
        if p.stance == "neutro":
            continue
        for t in p.tickers:
            by_key[(t, p.stance)].append(p)
    out: list[Campaign] = []
    for (ticker, stance), plist in by_key.items():
        plist.sort(key=lambda p: p.ts)
        i = 0
        while i < len(plist):
            start = plist[i].ts
            group = [plist[i]]
            j = i + 1
            while j < len(plist) and plist[j].ts - start <= timedelta(hours=window_hours):
                group.append(plist[j]); j += 1
            first_by_author: dict[str, datetime] = {}
            for p in group:
                first_by_author.setdefault(p.author_key, p.ts)
            if len(first_by_author) >= min_authors:
                ordered = sorted(first_by_author.items(), key=lambda kv: kv[1])
                leader = ordered[0][0]
                out.append(Campaign(
                    ticker=ticker, stance=stance, start=start, end=group[-1].ts,
                    authors=[a for a, _ in ordered], posts=group,
                    reach=sum(p.engagement for p in group), leader=leader,
                    lag_minutes=[(t - ordered[0][1]).total_seconds() / 60 for _, t in ordered],
                ))
                i = j
            else:
                i += 1
    return sorted(out, key=lambda c: c.start)


class CoMentionGraph:
    """Grafo não direcionado: peso = nº de campanhas em que o par participou junto.
    `lead` conta quantas vezes A postou antes de B no mesmo ativo (direcional)."""

    def __init__(self) -> None:
        self.weight: dict[tuple[str, str], int] = defaultdict(int)
        self.lead: dict[tuple[str, str], int] = defaultdict(int)
        self.nodes: set[str] = set()

    @classmethod
    def from_campaigns(cls, campaigns: list[Campaign]) -> "CoMentionGraph":
        g = cls()
        for c in campaigns:
            g.nodes.update(c.authors)
            for a, b in combinations(c.authors, 2):
                g.weight[tuple(sorted((a, b)))] += 1
                g.lead[(a, b)] += 1   # a veio antes de b (authors está em ordem temporal)
        return g

    def neighbors(self, node: str, min_weight: int = 1) -> list[tuple[str, int]]:
        out = []
        for (a, b), w in self.weight.items():
            if w < min_weight:
                continue
            if a == node: out.append((b, w))
            elif b == node: out.append((a, w))
        return sorted(out, key=lambda t: -t[1])

    def leaders(self) -> list[tuple[str, int]]:
        """Quem mais aparece antes dos outros: provável origem das campanhas."""
        score: dict[str, int] = defaultdict(int)
        for (a, b), n in self.lead.items():
            score[a] += n
            score[b] -= n
        return sorted(score.items(), key=lambda t: -t[1])


def clusters(graph: CoMentionGraph, min_weight: int = 2) -> list[list[str]]:
    """Componentes conexos usando só arestas com peso >= min_weight: grupos que
    repetidamente postam juntos. Peso 1 pode ser coincidência; 2+ é padrão."""
    adj: dict[str, set[str]] = defaultdict(set)
    for (a, b), w in graph.weight.items():
        if w >= min_weight:
            adj[a].add(b); adj[b].add(a)
    seen: set[str] = set()
    out: list[list[str]] = []
    for n in graph.nodes:
        if n in seen or n not in adj:
            continue
        stack, comp = [n], []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x); comp.append(x)
            stack.extend(adj[x] - seen)
        if len(comp) >= 2:
            out.append(sorted(comp))
    return sorted(out, key=len, reverse=True)
