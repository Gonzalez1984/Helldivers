from crawler.parse import parse_warbond_rewards, parse_stratagem_catalog

W='''<table><tr><th>Icon</th><th>Item</th><th>Type</th><th>Cost</th></tr><tr><td></td><td><a href="/wiki/Test_Gun">Test Gun</a></td><td>Assault Rifle</td><td>20</td></tr><tr><td></td><td><a href="/wiki/Test_Cape">Test Cape</a></td><td>Cape</td><td>20</td></tr></table>'''
assert [x.title for x in parse_warbond_rewards(W,'WB')]==['Test Gun']
S='''<table><tr><th>Icon</th><th>Name</th><th>Stratagem Code</th><th>Base Cooldown</th><th>Source</th></tr><tr><td></td><td><a href="/wiki/Test_Strata">Test Strata</a></td><td><img alt="Stratagem Arrow Up.svg"><img alt="Stratagem Arrow Right.svg"></td><td>60s</td><td>Bridge</td></tr></table>'''
x=parse_stratagem_catalog(S)[0]
assert x.title=='Test Strata' and x.stratagem_code==['Up','Right'] and x.source=='Bridge'
print('smoke tests passed')
