from __future__ import annotations
import hashlib, json, time, os
from pathlib import Path
from typing import Any
import requests
from .config import API, CACHE, USER_AGENT, CACHE_TTL_SECONDS

class WikiError(RuntimeError): pass

class WikiAPI:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.s.headers.update({'User-Agent': USER_AGENT, 'Accept': 'application/json'})

    def _cache_path(self, params: dict[str, Any]) -> Path:
        raw = json.dumps(params, sort_keys=True, ensure_ascii=False).encode()
        return CACHE / 'api' / f'{hashlib.sha256(raw).hexdigest()}.json'

    def get(self, params: dict[str, Any], *, cache=True) -> dict[str, Any]:
        path = self._cache_path(params); path.parent.mkdir(parents=True, exist_ok=True)
        if cache and path.exists() and (time.time() - path.stat().st_mtime) < CACHE_TTL_SECONDS:
            return json.loads(path.read_text(encoding='utf-8'))
        p = dict(params); p.setdefault('format','json'); p.setdefault('formatversion','2')
        last = None
        for attempt in range(5):
            try:
                r = self.s.get(API, params=p, timeout=45)
                r.raise_for_status(); data = r.json()
                if 'error' in data: raise WikiError(str(data['error']))
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                time.sleep(.12); return data
            except Exception as e:
                last = e
                time.sleep(1.5 * (attempt + 1))
        raise WikiError(f'Wiki API failed: {last}')

    def query_all(self, params: dict[str, Any], key: str) -> list[dict]:
        out=[]; cont={}
        while True:
            p=dict(params); p.update(cont); data=self.get(p); out.extend(data.get('query',{}).get(key,[]))
            if 'continue' not in data: return out
            cont=data['continue']

    def category_members(self, category: str, namespace=0) -> list[str]:
        rows=self.query_all({'action':'query','list':'categorymembers','cmtitle':f'Category:{category}','cmnamespace':str(namespace),'cmlimit':'max'},'categorymembers')
        return [x['title'] for x in rows]

    def pages(self, titles: list[str], *, prop='info|categories|images|revisions', rvprop='ids|timestamp') -> list[dict]:
        out=[]
        for i in range(0,len(titles),50):
            data=self.get({'action':'query','prop':prop,'titles':'|'.join(titles[i:i+50]),'inprop':'url','rvprop':rvprop,'rvslots':'main'})
            out.extend(data.get('query',{}).get('pages',[]))
        return out

    def rendered_html(self, title: str) -> str:
        data=self.get({'action':'parse','page':title,'prop':'text'})
        return data['parse']['text']

    def wikitext(self, title: str) -> str:
        data=self.get({'action':'parse','page':title,'prop':'wikitext'})
        return data['parse']['wikitext']['*']

    def imageinfo(self, filename: str, width=1200) -> dict:
        title=filename if filename.startswith('File:') else f'File:{filename}'
        data=self.get({'action':'query','titles':title,'prop':'imageinfo','iiprop':'url|mime|size|sha1|extmetadata','iiurlwidth':str(width)})
        page=next(iter(data['query']['pages'].values())); info=page.get('imageinfo')
        if not info: raise WikiError(f'No imageinfo for {filename}')
        return info[0]
