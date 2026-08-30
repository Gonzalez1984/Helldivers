from pathlib import Path
BASE='https://helldivers.wiki.gg/wiki/'
API='https://helldivers.wiki.gg/api.php'
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'cache';OUTPUT=ROOT/'output';STATE=ROOT/'state';PDF_NAME=OUTPUT/'helldivers_loadout.pdf';OWNED_NAME=STATE/'owned.json'
USER_AGENT='HelldiversLoadoutCrawler/2.0 (personal printable loadout reference; contact via project README)'
WIKI_LICENSE='CC BY-NC-SA 4.0'
CACHE_TTL_SECONDS=6*60*60
for p in (CACHE,OUTPUT,STATE):p.mkdir(parents=True,exist_ok=True)
