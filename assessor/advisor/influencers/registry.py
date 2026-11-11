"""Registro de influenciadores e grupos.

Só perfis PÚBLICOS e posts PÚBLICOS. O registro começa vazio: você cadastra
quem acompanha (handle, plataforma, país, grupos declarados). O sistema
preenche o resto com dados: rede de co-menção, histórico de acerto,
assinatura de pump. Nada aqui afirma vínculo entre pessoas sem evidência
nos dados; o campo `groups` é o que é declarado publicamente, e os
clusters descobertos ficam separados (`network.clusters`).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Influencer:
    handle: str                       # ex.: "@fulano" (sem o @ também funciona)
    platform: str                     # x | youtube | instagram | telegram | reddit | tiktok | podcast
    country: str = "BR"               # BR | US | global
    name: str = ""
    followers: int = 0
    focus: list[str] = field(default_factory=list)   # acoes_br | acoes_us | fiis | cripto | opcoes
    groups: list[str] = field(default_factory=list)  # grupos/comunidades DECLARADOS publicamente
    disclosed_affiliations: list[str] = field(default_factory=list)  # casa de análise, corretora, projeto cripto
    is_registered_analyst: bool = False   # CVM/APIMEC no BR; relevante para peso
    feeds: list[str] = field(default_factory=list)   # URLs/handles de coleta (RSS, canal t.me/s/..., etc.)
    notes: str = ""

    @property
    def key(self) -> str:
        return f"{self.platform}:{self.handle.lstrip('@').lower()}"


class InfluencerRegistry:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else None
        self._items: dict[str, Influencer] = {}
        if self.path and self.path.exists():
            for row in json.loads(self.path.read_text(encoding="utf-8")):
                self.add(Influencer(**row), save=False)

    def add(self, inf: Influencer, save: bool = True) -> None:
        self._items[inf.key] = inf
        if save:
            self.save()

    def get(self, key: str) -> Influencer | None:
        return self._items.get(key)

    def all(self) -> list[Influencer]:
        return list(self._items.values())

    def by_group(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for inf in self._items.values():
            for g in inf.groups:
                out.setdefault(g, []).append(inf.key)
        return out

    def by_country(self, country: str) -> list[Influencer]:
        return [i for i in self._items.values() if i.country == country]

    def save(self) -> None:
        if self.path:
            self.path.write_text(json.dumps([asdict(i) for i in self._items.values()],
                                            ensure_ascii=False, indent=2), encoding="utf-8")
