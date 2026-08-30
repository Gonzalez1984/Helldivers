from __future__ import annotations
import argparse
from .api import WikiAPI
from .warbonds import discover_warbonds, choose_warbonds
from .catalog import load_catalog
from .ownership import Ownership, choose_extras, build_owned, save, DEFAULT_WARBONDS
from .extract import resolve_image, extract_warbond
from .validate import validate
from .pdf import build_pdf


def main():
    ap = argparse.ArgumentParser(description='Build a strictly owned Helldivers 2 loadout PDF from helldivers.wiki.gg')
    ap.add_argument('--warbonds', help='Exact comma-separated Warbond names; otherwise interactive.')
    ap.add_argument('--default-profile', action='store_true', help='Use the configured 12-Warbond profile from the project.')
    ap.add_argument('--refresh', action='store_true', help='Ignore cached API responses and fetch fresh wiki data.')
    ap.add_argument('--strict-stratagem-ownership', action='store_true', help='Ask about non-Warbond stratagem ownership instead of assuming all ordinary non-mission stratagems are owned.')
    args = ap.parse_args()

    api = WikiAPI()
    if args.refresh:
        api.get = lambda params, cache=True: WikiAPI.get(api, params, cache=False)

    wbs = discover_warbonds(api)
    if args.default_profile:
        preset = DEFAULT_WARBONDS
    elif args.warbonds is not None:
        preset = [x.strip() for x in args.warbonds.split(',') if x.strip()]
    else:
        preset = None
    owned_wbs = choose_warbonds(wbs, preset)

    print('\n=== ETAP 2 — POBIERANIE WARBOND REWARD TABLES ===')
    wb_items=[]
    for wb in owned_wbs:
        rows=extract_warbond(api,wb)
        print(f'  {wb}: {len(rows)} relevant reward rows')
        wb_items.extend(rows)
    wb_keys={x.key for x in wb_items}
    print('  unique owned-by-Warbond item keys:',len(wb_keys))

    print('\n=== ETAP 3 — POBIERANIE KATALOGÓW ===')
    catalogs={}
    for kind in ('primary','secondary','throwable','armor','booster','stratagem'):
        print('  ',kind); catalogs[kind]=load_catalog(api,kind); print('     ',len(catalogs[kind]),'entries')

    strict = args.strict_stratagem_ownership
    extras = choose_extras(catalogs['stratagem'], owned_wbs) if strict else set()
    ownership=Ownership(
        owned_wbs, extras, True,
        assume_all_non_mission_stratagems=not strict,
    )
    save(ownership)

    print('\n=== ETAP 5 — WYLICZANIE POSIADANEGO SPRZĘTU ===')
    owned=build_owned(
        catalogs, owned_wbs, extras, True, wb_keys,
        assume_all_non_mission_stratagems=not strict,
    )
    print('Owned candidates:',len(owned))

    print('\n=== ETAP 6 — WERYFIKACJA OBRAZÓW ===')
    resolved=[]
    for i,x in enumerate(owned,1):
        print(f'[{i}/{len(owned)}] {x.title}')
        resolved.append(resolve_image(api,x))
    validate(catalogs,resolved,owned_wbs,extras)

    print('\n=== ETAP 7 — PDF ===')
    pdf=build_pdf(resolved,owned_wbs,extras)
    print('PDF:',pdf)
    for k in ('stratagem','primary','secondary','throwable','armor','booster'):
        print(f'  {k:10}: {sum(x.kind==k for x in resolved)}')

if __name__=='__main__': main()
