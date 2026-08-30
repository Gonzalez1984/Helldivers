from __future__ import annotations

import re

from .api import WikiAPI
from .model import Item


def discover_stratagems(api: WikiAPI) -> list[Item]:
    titles = api.category_members("Stratagems")
    out = []

    # Category:Stratagems contains exactly the stratagem article index plus the
    # umbrella page. We exclude obvious non-equipment helper pages.
    for title in titles:
        if title in {"Stratagems"}:
            continue
        if any(x in title for x in ("Stratagem Arrow", "April Fools/")):
            continue
        out.append(Item(
            title=title,
            kind="stratagem",
            url=f"https://helldivers.wiki.gg/wiki/{title.replace(' ', '_')}",
        ))
    return out


def stratagem_owned_via_base_or_extra(item: Item, extras: set[str]) -> bool:
    # We do NOT assume that every stratagem is personally owned.
    # The user can explicitly select non-Warbond stratagems.
    return item.title in extras
