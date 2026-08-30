from __future__ import annotations
from .api import WikiAPI
from .parse import parse_catalog, parse_stratagem_catalog

# These pages are stable semantic indexes on the wiki. We use their rendered
# tables instead of scraping visual cards or guessing from category names.
CATALOGS={
 'primary': 'Primary weapons',
 'secondary': 'Secondary weapons',
 'throwable': 'Throwables',
 'armor': 'Body armor',
 'booster': 'Boosters',
 'stratagem': 'Stratagem',
}

def load_catalog(api:WikiAPI,kind:str):
    html=api.rendered_html(CATALOGS[kind])
    if kind=='stratagem': return parse_stratagem_catalog(html)
    return parse_catalog(html,kind)
