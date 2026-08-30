from __future__ import annotations
import re
from .api import WikiAPI

def discover_warbonds(api:WikiAPI)->list[str]:
    html=api.rendered_html('Warbonds')
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'lxml')
    out=[]
    for a in soup.select('a[href*="/wiki/"]'):
        href=a.get('href',''); text=a.get_text(' ',strip=True)
        if not href or not text: continue
        title=href.split('/wiki/',1)[1].split('#',1)[0].replace('_',' ')
        if title.endswith(' Warbond') or title.endswith(' Legendary Warbond') or title in {'Helldivers Mobilize!'}:
            name=text.strip()
            if name not in out: out.append(name)
    if not out: raise RuntimeError('Could not discover Warbonds from wiki page.')
    return out

def choose_warbonds(all_warbonds:list[str],preset:list[str]|None=None)->list[str]:
    if preset is not None:
        bad=[x for x in preset if x not in all_warbonds]
        if bad: raise ValueError(f'Unknown Warbond(s): {bad}')
        return list(dict.fromkeys(preset))
    print('\n=== ETAP 1 — POSIADANE WARBONDY ===')
    for i,x in enumerate(all_warbonds,1): print(f'{i:2}. {x}')
    raw=input('\nNumery (np. 1,2,5): ').strip()
    if not raw:return []
    ids=[int(v.strip()) for v in raw.split(',') if v.strip()]
    if any(i<1 or i>len(all_warbonds) for i in ids): raise ValueError('Nieprawidłowy numer Warbonda.')
    return [all_warbonds[i-1] for i in dict.fromkeys(ids)]
