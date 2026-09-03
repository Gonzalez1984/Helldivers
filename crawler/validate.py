from __future__ import annotations
from collections import Counter
from .model import Item
from .ownership import is_mission_stratagem, _normalize_warbond_text

def validate(catalogs:dict[str,list[Item]],owned:list[Item],warbonds:list[str],extras:set[str],assume_all_non_mission_stratagems=True):
    # An empty catalog for any kind almost always means a wiki page/category
    # name went stale or the page structure changed (as happened with the
    # 'Throwables' page), not that the game genuinely has zero items of that
    # kind. load_catalog() itself stays lenient (catches fetch errors and
    # returns [] so one bad page doesn't crash catalog loading for the rest),
    # but silently shipping a PDF missing an entire category is worse than
    # failing loudly here, where the user gets an actionable error instead of
    # just noticing "booster: 0" in the final printed summary.
    empty_kinds=[kind for kind,items in catalogs.items() if not items]
    if empty_kinds:
        raise RuntimeError(f'Catalog(s) came back empty, likely a stale wiki page/category name: {empty_kinds}')
    if not owned: raise RuntimeError('Ownership result is empty; refusing to generate PDF.')
    keys=[x.key for x in owned]; dup=[k for k,n in Counter(keys).items() if n>1]
    if dup: raise RuntimeError(f'Duplicate canonical IDs: {dup}')
    for x in owned:
        if not x.url.startswith('https://helldivers.wiki.gg/wiki/'): raise RuntimeError(x.url)
        if x.kind=='stratagem':
            has_evidence = x.source or x.title in extras or (assume_all_non_mission_stratagems and not is_mission_stratagem(x))
            if not has_evidence: raise RuntimeError(f'No ownership evidence: {x.title}')
    # Ensure every selected Warbond is actually represented in the catalog.
    for wb in warbonds:
        if not any((_normalize_warbond_text(wb) in _normalize_warbond_text(x.source)) for xs in catalogs.values() for x in xs):
            raise RuntimeError(f'Selected Warbond has no recognized catalog rewards: {wb}')
    # Boosters are loadout equipment, so they are subject to the same strict
    # Warbond/source ownership validation as weapons and armor.
    # Never silently include an item from an unselected Warbond.
    selected={_normalize_warbond_text(w) for w in warbonds}
    bad=[]
    for x in owned:
        s=_normalize_warbond_text(x.source)
        if x.kind!='stratagem' and any(token in s for token in ('warbond','mobilize','veterans','cutting edge','democratic','polar','viper','freedom','chemical','truth','urban','servants','borderline','masters','force of law','control group','dust devils','python commandos','redacted regiment','siege breakers','entrenched division','exo experts','obedient democracy','righteous revenants','castellan')):
            if not any(w in s for w in selected):
                bad.append(x.title)
    if bad: raise RuntimeError(f'Items appear to come from unselected Warbonds: {bad[:20]}')
