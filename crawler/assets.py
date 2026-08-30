from __future__ import annotations
import hashlib
from pathlib import Path
import requests
from .config import CACHE,USER_AGENT

def download(url:str,key:str)->Path:
    folder=CACHE/'images'; folder.mkdir(parents=True,exist_ok=True)
    ext='.png'
    for e in ('.webp','.jpeg','.jpg','.png','.svg'):
        if e in url.lower(): ext=e; break
    p=folder/(hashlib.sha256(key.encode()).hexdigest()+ext)
    if p.exists(): return p
    r=requests.get(url,headers={'User-Agent':USER_AGENT},timeout=60); r.raise_for_status(); p.write_bytes(r.content); return p
