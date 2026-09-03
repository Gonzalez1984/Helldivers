from __future__ import annotations
from .api import WikiAPI
from .parse import parse_catalog, parse_stratagem_catalog, parse_weapons_from_category

# These pages are stable semantic indexes on the wiki. We use their rendered
# tables instead of scraping visual cards or guessing from category names.
CATALOGS={
 'primary': 'Primary Weapons',
 'secondary': 'Secondary Weapons',
 'armor': 'Armor',
 'booster': 'Boosters',
 'stratagem': 'Stratagems',
}

# Category names used for kinds that are more reliably enumerated via
# MediaWiki category membership than by parsing a page's HTML table.
# "Throwable" is a redirect to a section of the Weapons page (no table of
# its own), but Category:Throwables lists every throwable item directly.
CATEGORY_CATALOGS={
 'primary': 'Primary Weapons',
 'secondary': 'Secondary Weapons',
 'throwable': 'Throwables',
}

def load_catalog(api: WikiAPI, kind: str):
    '''Load catalog for the given kind. Returns empty list if page not found.'''
    try:
        # Weapons and throwables are loaded from categories instead of table
        # pages, since their table-based pages are missing or are redirects.
        if kind in CATEGORY_CATALOGS:
            titles = api.category_members(CATEGORY_CATALOGS[kind])
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
