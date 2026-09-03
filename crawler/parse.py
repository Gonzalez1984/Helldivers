from __future__ import annotations
import re
from urllib.parse import unquote
from bs4 import BeautifulSoup
from .model import Item

BASE='https://helldivers.wiki.gg/wiki/'

KIND_BY_TABLE={
    'primary weapons':'primary','primary weapon':'primary',
    'secondary weapons':'secondary','secondary weapon':'secondary',
    'throwables':'throwable','throwable weapons':'throwable','throwable weapon':'throwable',
    'body armor':'armor','armor':'armor','armors':'armor',
    'boosters':'booster','booster':'booster',
    'stratagems':'stratagem','stratagem':'stratagem',
}

def clean(s:str)->str:
    return re.sub(r'\s+',' ',BeautifulSoup(s,'html.parser').get_text(' ',strip=True)).strip()

def canonical_title(href:str, text:str)->str:
    if href and '/wiki/' in href:
        x=href.split('/wiki/',1)[1].split('#',1)[0]
        x=unquote(x).replace('_',' ')
        return clean(x)
    return clean(text)

def page_url(title:str)->str:
    return BASE + title.replace(' ','_')

def table_rows(html:str):
    soup=BeautifulSoup(html,'lxml')
    for table in soup.select('table'):
        headers=[clean(x.get_text(' ',strip=True)).casefold() for x in table.select('tr:first-child th')]
        if not headers: continue
        rows=[]
        for tr in table.select('tr')[1:]:
            cells=tr.find_all(['td','th'])
            if len(cells)<2: continue
            row={}
            for i,c in enumerate(cells[:len(headers)]): row[headers[i]]=c
            rows.append(row)
        yield headers, rows

def infer_kind(headers:list[str], title:str='', page_title:str='')->str|None:
    hs=' '.join(headers).casefold()
    p=(page_title+' '+title).casefold()
    if 'stratagem code' in hs or 'permit type' in hs: return 'stratagem'
    if 'passive' in hs and 'armor' in hs and 'speed' in hs: return 'armor'
    if 'type' in hs and 'cost' in hs and ('source' in hs or 'acquisition' in hs):
        if any(x in p for x in ('armor','warbond')): return None
    if 'source' in hs and 'cost' in hs:
        if any(x in p for x in ('primary','secondary','throwable','armor')): return None
    return None

def extract_link(cell) -> tuple[str,str]|None:
    a=cell.find('a',href=True)
    if not a: return None
    title=canonical_title(a['href'],a.get_text(' ',strip=True))
    if not title or title.startswith(('Category:','File:','Template:')): return None
    return title,a['href']

def classify_warbond_type(type_text:str, item_title:str='')->str|None:
    t=type_text.casefold()
    if any(x in t for x in ('medium armor','light armor','heavy armor','armor')): return 'armor'
    if any(x in t for x in ('assault rifle','marksman','submachine','shotgun','explosive','energy','special primary','rifle','primary')): return 'primary'
    if any(x in t for x in ('pistol','melee','special secondary','secondary')): return 'secondary'
    if any(x in t for x in ('grenade','throwable')): return 'throwable'
    if 'booster' in t: return 'booster'
    if 'stratagem' in t: return 'stratagem'
    return None

def parse_warbond_rewards(html:str, warbond:str)->list[Item]:
    out=[]
    for headers,rows in table_rows(html):
        # Warbond reward tables expose Item/Type/Cost. We only accept rows with
        # an actual wiki link and a type that maps unambiguously to our target.
        if 'item' not in headers or 'type' not in headers: continue
        for row in rows:
            link=extract_link(row['item']); typ=clean(row['type'].get_text(' ',strip=True))
            if not link: continue
            title,_=link; kind=classify_warbond_type(typ,title)
            if not kind: continue
            out.append(Item(title,kind,page_url(title),source=warbond,acquisition=f'Warbond: {warbond}',notes=f'Warbond reward type: {typ}'))
    # dedupe; a warbond can show the same item in more than one visual/table context.
    return list({x.key:x for x in out}.values())

def parse_catalog(html:str, kind:str, default_source='') -> list[Item]:
    out=[]
    for headers,rows in table_rows(html):
        if 'name' not in headers and 'item' not in headers and 'booster' not in headers: continue
        namecol=None
        if 'name' in headers: namecol='name'
        elif 'item' in headers: namecol='item'
        elif 'booster' in headers: namecol='booster'
        if not namecol: continue
        for row in rows:
            link=extract_link(row[namecol]);
            if not link: continue
            title,_=link
            vals={k:clean(v.get_text(' ',strip=True)) for k,v in row.items()}
            source=vals.get('source',vals.get('acquisition',vals.get('warbond',default_source)))
            item=Item(title,kind,page_url(title),source=source,acquisition=source,stats=vals)
            # Some catalog tables expose a dedicated Icon column with a direct
            # File: link. Prefer that over guessing from page image galleries,
            # since it's unambiguous and works even when the icon is an .svg.
            if 'icon' in headers:
                icon_cell=row.get('icon')
                if icon_cell:
                    icon_link=icon_cell.find('a', href=True)
                    if icon_link and '/wiki/File:' in icon_link['href']:
                        item.stats['icon_file']=icon_link['href'].split('/wiki/File:',1)[1]
            out.append(item)
    return list({x.key:x for x in out}.values())

def parse_stratagem_catalog(html:str)->list[Item]:
    out=[]
    soup=BeautifulSoup(html,'lxml')
    current_section=''
    for node in soup.select('h1,h2,h3,h4,h5,h6,table'):
        if node.name.startswith('h'):
            current_section=clean(node.get_text(' ',strip=True))
            continue
        table=node
        headers=[clean(x.get_text(' ',strip=True)).casefold() for x in table.select('tr:first-child th')]
        if not {'name','stratagem code'}.issubset(set(headers)): continue
        for tr in table.select('tr')[1:]:
            cells=tr.find_all(['td','th'])
            if len(cells)<len(headers): continue
            row={headers[i]:cells[i] for i in range(len(headers))}
            link=extract_link(row['name'])
            if not link: continue
            title,_=link
            vals={k:clean(v.get_text(' ',strip=True)) for k,v in row.items()}
            vals['section']=current_section
            code=[]
            for img in row['stratagem code'].select('img'):
                alt=img.get('alt') or img.get('title') or ''
                src=img.get('src','')
                token=(alt or src.rsplit('/',1)[-1]).replace('.svg','').replace('Stratagem Arrow ','').strip()
                if token: code.append(token)
            # Extract icon URL from Icon column if present
            icon_file=None
            if 'icon' in headers:
                icon_cell=row.get('icon')
                if icon_cell:
                    icon_link=icon_cell.find('a', href=True)
                    if icon_link and '/wiki/File:' in icon_link['href']:
                        icon_file=icon_link['href'].split('/wiki/File:',1)[1]
            source=vals.get('source','')
            # The catalog's Objective/Mission tables are not permanent loadout
            # options. Keep them in the parser's data model only long enough for
            # validation, where they are rejected from ownership.
            item=Item(title,'stratagem',page_url(title),source=source,acquisition=source,stats=vals,stratagem_code=code)
            if icon_file:
                item.stats['icon_file']=icon_file
            out.append(item)
    return list({x.key:x for x in out}.values())

def parse_weapons_from_category(titles:list[str], kind:str)->list[Item]:
    '''Parse weapons from category member list. All base weapons are free/starter equipment.'''
    out=[]
    for title in titles:
        out.append(Item(title,kind,page_url(title),source='Free Starter Equipment',acquisition='Free',stats={}))
    return out
