from __future__ import annotations
from .api import WikiAPI
from .parse import parse_catalog, parse_stratagem_catalog, parse_weapons_from_category

# These pages are stable semantic indexes on the wiki. We use their rendered
# tables instead of scraping visual cards or guessing from category names.
CATALOGS={
 'primary': 'Primary Weapons',
 'secondary': 'Secondary Weapons',
 'throwable': 'Throwables',
 'armor': 'Armor',
 'booster': 'Boosters',
 'stratagem': 'Stratagems',
}

def load_catalog(api: WikiAPI, kind: str):
    '''Load catalog for the given kind. Returns empty list if page not found.'''
    try:
        # Weapons are now loaded from categories instead of table pages
        if kind in ('primary', 'secondary'):
            cat_name = 'Primary Weapons' if kind == 'primary' else 'Secondary Weapons'
            titles = api.category_members(cat_name)
            return parse_weapons_from_category(titles, kind)
        
        html = api.rendered_html(CATALOGS[kind])
        if kind == 'stratagem':
            return parse_stratagem_catalog(html)
        result = parse_catalog(html, kind)
        return result if result else []
    except Exception as e:
        # If catalog page fails, return empty list rather than crashing
        # This handles wiki structure changes gracefully
        print(f'    Warning: Could not load {kind} catalog: {str(e)[:60]}')
        return []
