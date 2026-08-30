from __future__ import annotations
from dataclasses import dataclass
import json
from .config import OWNED_NAME
from .model import Item

DEFAULT_WARBONDS = [
    'Helldivers Mobilize!', 'Steeled Veterans', 'Urban Legends',
    'Servants of Freedom', 'Borderline Justice', 'Control Group', 'Dust Devils',
    'Python Commandos', 'Siege Breakers', 'Entrenched Division',
]

@dataclass
class Ownership:
    warbonds: list[str]
    extras: set[str]
    base: bool = True
    assume_all_non_mission_stratagems: bool = True
    version: int = 4


def save(o: Ownership):
    OWNED_NAME.parent.mkdir(parents=True, exist_ok=True)
    OWNED_NAME.write_text(json.dumps({
        'version': o.version,
        'base': o.base,
        'warbonds': o.warbonds,
        'extras': sorted(o.extras),
        'assume_all_non_mission_stratagems': o.assume_all_non_mission_stratagems,
    }, ensure_ascii=False, indent=2), encoding='utf-8')


def choose_extras(items: list[Item], selected_warbonds: list[str] | None = None) -> set[str]:
    # Retained for users who want strict personal ownership instead of the
    # user's requested "all basic + acquired along the way" assumption.
    selected_warbonds = selected_warbonds or []
    rows = [x for x in items if x.kind == 'stratagem' and not is_mission_stratagem(x)]
    rows = [x for x in rows if not source_matches_warbond(x.source, selected_warbonds)]
    rows = sorted({x.key: x for x in rows}.values(), key=lambda x: x.title.casefold())
    print('\n=== DODATKOWE STRATAGEMY ===')
    print('Zaznacz tylko rzeczy, które faktycznie masz. Enter = nic.')
    for i, x in enumerate(rows, 1): print(f'{i:3}. {x.title} [{x.source or "unknown source"}]')
    raw = input('\nNumery: ').strip()
    if not raw:
        return set()
    ids = [int(v.strip()) for v in raw.split(',') if v.strip()]
    if any(i < 1 or i > len(rows) for i in ids):
        raise ValueError('Nieprawidłowy numer.')
    return {rows[i - 1].title for i in ids}


def source_matches_warbond(source: str, warbonds: list[str] | set[str]) -> bool:
    s = (source or '').casefold()
    return any(w.casefold() in s for w in warbonds)


def is_mission_stratagem(item: Item) -> bool:
    s = ' '.join([
        item.title,
        item.source or '',
        item.stats.get('section', '') if item.stats else '',
        item.stats.get('category', '') if item.stats else '',
    ]).casefold()
    mission_terms = (
        'mission stratagem', 'mission', 'objective', 'temporary permit',
        'weapons augmentation', 'major order temporary',
    )
    return any(t in s for t in mission_terms)


def owns_by_source(item: Item, selected_warbonds: set[str], base=True,
                   assume_all_non_mission_stratagems=True) -> bool:
    if item.kind == 'stratagem':
        if is_mission_stratagem(item):
            return False
        if source_matches_warbond(item.source, selected_warbonds):
            return True
        # User explicitly asked us to assume all ordinary/basic stratagems and
        # things acquired along the way are already owned. This covers the
        # normal Ship Management tree, including Support Weapons, Backpacks,
        # Eagles, Orbitals, Sentries, Vehicles and Emplacements.
        if base and assume_all_non_mission_stratagems:
            return True
        return False

    if source_matches_warbond(item.source, selected_warbonds):
        return True
    # Explicitly reject items from unselected warbonds
    warbond_keywords = ('warbond','mobilize','veterans','cutting edge','democratic','polar','viper','freedom','chemical','truth','urban','servants','borderline','masters','force of law','control group','dust devils','python commandos','redacted regiment','siege breakers','entrenched division','exo experts','obedient democracy','righteous revenants','castellan')
    s = (item.source or '').casefold()
    if any(token in s for token in warbond_keywords):
        return False
    if base and any(k in s for k in ('starter equipment', 'free')):
        return True
    return False


def build_owned(catalogs: dict[str, list[Item]], selected_warbonds: list[str],
                extras: set[str], base=True, warbond_keys: set[str] | None = None,
                assume_all_non_mission_stratagems=True) -> list[Item]:
    wb = set(selected_warbonds)
    warbond_keys = warbond_keys or set()
    out: list[Item] = []

    for kind, items in catalogs.items():
        for x in items:
            if x.kind == 'stratagem' and is_mission_stratagem(x):
                continue
            if x.kind == 'stratagem' and x.title in extras:
                out.append(x)
                continue
            if x.key in warbond_keys or owns_by_source(
                x, wb, base,
                assume_all_non_mission_stratagems=assume_all_non_mission_stratagems,
            ):
                out.append(x)

    # Warbond reward extraction is authoritative for ownership. The catalog
    # may use a more verbose source label, so keep an exact key match as well.
    for items in catalogs.values():
        for x in items:
            if x.key in warbond_keys and x not in out:
                out.append(x)

    return list({x.key: x for x in out}.values())
