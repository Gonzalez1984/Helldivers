from __future__ import annotations
import re
from .api import WikiAPI
from .model import Item
from .parse import parse_warbond_rewards

# Image ranking is deliberately conservative: we want the actual item render,
# not a UI icon, logo, banner or unrelated gallery image.
BAD=('arrow','fallback','background','logo','banner','medal','icon background','map','flag','template')
PREF_BY_KIND={
 'primary':('primary render','primary weapon','weapon render','render'),
 'secondary':('secondary render','secondary weapon','weapon render','render'),
 'throwable':('throwable render','grenade render','throwable','render'),
 'booster':('booster render','booster'),
 'armor':('armor set','body armor','armor render','render'),
 'stratagem':('stratagem icon','icon'),
}

def _score(filename:str,kind:str)->int:
    n=filename.casefold(); score=0
    if any(b in n for b in BAD): score-=100
    for i,p in enumerate(PREF_BY_KIND[kind]):
        if p in n: score += 40-i*5
    if n.endswith('.svg'): score-=50
    return score

def resolve_image(api:WikiAPI,item:Item)->Item:
    # If the catalog table exposed a dedicated Icon column with a direct
    # File: link, prefer it over guessing from the page's image gallery —
    # it's unambiguous and works even when the icon is an .svg (boosters,
    # stratagems), which page-image scoring below would otherwise skip.
    icon_file=item.stats.get('icon_file') if item.stats else None
    if icon_file:
        try:
            info=api.imageinfo(icon_file, width=64)
            if isinstance(info, dict) and info.get('mime','').startswith('image/'):
                item.image_file=icon_file
                item.image_url=info.get('thumburl') or info.get('url')
                item.image_sha1=info.get('sha1')
                item.image_license=(info.get('extmetadata',{}).get('LicenseShortName',{}).get('value') or '')
                return item
        except Exception:
            pass
    
    page=api.pages([item.title],prop='images')
    if not page: raise RuntimeError(f'No page image list: {item.title}')
    filenames=[x['title'] for x in page[0].get('images',[])]
    if not filenames: raise RuntimeError(f'No images: {item.title}')
    candidates=sorted(filenames,key=lambda x:_score(x,item.kind),reverse=True)
    errors=[]
    for filename in candidates[:30]:
        try:
            # Skip SVG files - they can't be embedded directly in PDFs
            if filename.lower().endswith('.svg'):
                continue
            info=api.imageinfo(filename)
            # imageinfo returns a dict with image info
            if not isinstance(info, dict):
                errors.append(f'imageinfo returned non-dict: {type(info)}')
                continue
            if not info.get('mime','').startswith('image/'): 
                continue
            if _score(filename,item.kind)<0: 
                continue
            item.image_file=filename
            item.image_url=info.get('thumburl') or info.get('url')
            item.image_sha1=info.get('sha1')
            item.image_license=(info.get('extmetadata',{}).get('LicenseShortName',{}).get('value') or '')
            return item
        except Exception as e: 
            errors.append(str(e))
    raise RuntimeError(f'No trustworthy image for {item.title}: {errors[-3:]}')

def extract_warbond(api:WikiAPI,warbond:str)->list[Item]:
    return parse_warbond_rewards(api.rendered_html(warbond),warbond)
