from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

Kind = Literal['primary','secondary','throwable','armor','booster','stratagem']

@dataclass
class Item:
    title: str
    kind: Kind
    url: str
    source: str = ''
    acquisition: str = ''
    image_file: str | None = None
    image_url: str | None = None
    image_sha1: str | None = None
    image_license: str | None = None
    categories: list[str] = field(default_factory=list)
    stats: dict[str, str] = field(default_factory=dict)
    stratagem_code: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)
    notes: str = ''

    @property
    def key(self) -> str:
        return f'{self.kind}:{self.title.casefold().strip()}'
