from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image as RImage,Table,TableStyle,PageBreak
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg
from reportlab.lib import colors
from .assets import download
from .config import PDF_NAME,WIKI_LICENSE
from .model import Item

SECTIONS=[('stratagem','STRATAGEMS'),('primary','PRIMARY'),('secondary','SECONDARY'),('throwable','GRENADES / THROWABLES'),('armor','ARMOR'),('booster','BOOSTERS')]

def fit_image(path:Path,mw,mh):
    with Image.open(path) as im:w,h=im.size
    s=min(mw/w,mh/h);return w*s,h*s

def compress_image(image_path: Path, max_width: int = 300, quality: int = 85) -> Path:
    '''Compress image to reduce PDF size while maintaining quality for display.'''
    try:
       with Image.open(image_path) as img:
           # Convert to RGB if necessary (for PNG with transparency)
           if img.mode in ('RGBA', 'LA', 'P'):
               rgb_img = Image.new('RGB', img.size, (255, 255, 255))
               rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
               img = rgb_img
            
           # Resize if too large
           if img.width > max_width:
               ratio = max_width / img.width
               new_height = int(img.height * ratio)
               img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
           # Save compressed version
           compressed_path = image_path.with_stem(image_path.stem + '_compressed')
           img.save(compressed_path, 'JPEG', quality=quality, optimize=True)
           return compressed_path
    except Exception as e:
       # If compression fails, return original
       return image_path

def _code(code):
    if not code:return ''
    symbols={'up':'↑','down':'↓','left':'←','right':'→','u':'↑','d':'↓','l':'←','r':'→'}
    return ' '.join(symbols.get(x.casefold(),x) for x in code)

def build_pdf(items:list[Item],warbonds:list[str],extras:set[str])->Path:
    doc=SimpleDocTemplate(str(PDF_NAME),pagesize=A4,leftMargin=8*mm,rightMargin=8*mm,topMargin=8*mm,bottomMargin=8*mm,title='Helldivers 2 Owned Loadout Manual')
    st=getSampleStyleSheet(); title=ParagraphStyle('T',parent=st['Title'],fontSize=18,leading=20,alignment=TA_CENTER); h=ParagraphStyle('H',parent=st['Heading1'],fontSize=14,leading=16,spaceAfter=4*mm); card=ParagraphStyle('C',parent=st['BodyText'],fontSize=7,leading=8); tiny=ParagraphStyle('S',parent=st['BodyText'],fontSize=5.2,leading=6)

    # Resolve the wiki's actual Stratagem Arrow SVGs once. These are the same
    # assets used by the wiki's stratagem tables, not recreated Unicode glyphs.
    arrow_drawings={}
    try:
        from .api import WikiAPI
        from .assets import download
        api=WikiAPI()
        from svglib.svglib import svg2rlg
        for name in ('Up','Down','Left','Right'):
            info=api.imageinfo(f'Stratagem Arrow {name}.svg',width=128)
            path=download(info.get('url') or info.get('thumburl'),f'arrow:{name}')
            drawing=svg2rlg(str(path))
            if drawing:
                scale=min(7*mm/max(drawing.width,1),7*mm/max(drawing.height,1));drawing.scale(scale,scale);arrow_drawings[name]=drawing
    except Exception:
        arrow_drawings={}

    def arrow_strip(code):
        if not code:return ''
        mapping={'up':'Up','down':'Down','left':'Left','right':'Right'}
        cells=[]
        fallback={'Up':'↑','Down':'↓','Left':'←','Right':'→'}
        for token in code:
            name=mapping.get(token.casefold(),token.title())
            cells.append(arrow_drawings.get(name,Paragraph(fallback.get(name,name),card)))
        t=Table([cells],colWidths=[8*mm]*len(cells),hAlign='LEFT')
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        return t

    story=[Paragraph('HELLDIVERS 2 — OWNED LOADOUT FIELD MANUAL',title),Spacer(1,2*mm),Paragraph('Generated from the current helldivers.wiki.gg semantic catalogs. Ownership is conservative: unproven items are excluded.',card),Paragraph('Warbonds: '+(', '.join(warbonds) if warbonds else 'none'),tiny),Paragraph('Generated: '+datetime.now(timezone.utc).isoformat(),tiny),Spacer(1,4*mm)]
    for kind,heading in SECTIONS:
        group=sorted([x for x in items if x.kind==kind],key=lambda x:x.title.casefold())
        if not group:continue
        story.append(Paragraph(heading,h))
        cols_per_row = 5 if kind=='stratagem' else 3
        rows=[];cells=[]
        for x in group:
            p=download(x.image_url,x.key)
            p=compress_image(p, max_width=150 if kind=='stratagem' else 300, quality=85)
            max_w = 25*mm if kind=='stratagem' else 42*mm
            max_h = 25*mm if kind=='stratagem' else 28*mm
            w,hh=fit_image(p,max_w,max_h); img=RImage(str(p),width=w,height=hh)
            extras_txt=''
            if kind=='stratagem': extras_txt=f'<br/>{_code(x.stratagem_code)}'
            stats=''
            if kind=='armor': stats=' · '.join(f'{k}: {v}' for k,v in x.stats.items() if k in ('armor','speed','stamina','passive'))
            if kind=='booster': stats=(x.stats.get('description','') or '')
            content=[img,Paragraph(f'<b>{x.title}</b>{extras_txt}<br/>{stats}<br/><font size="4.5">{x.acquisition or x.source}</font>',card)]
            if kind=='stratagem' and x.stratagem_code:
                content.insert(1,arrow_strip(x.stratagem_code))
            cells.append(content)
            if len(cells)==cols_per_row:rows.append(cells);cells=[]
        if cells:
            while len(cells)<cols_per_row:cells.append([])
            rows.append(cells)
        col_width = 40*mm if kind=='stratagem' else 64*mm
        t=Table(rows,colWidths=[col_width]*cols_per_row,hAlign='LEFT')
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BOX',(0,0),(-1,-1),.35,colors.grey),('INNERGRID',(0,0),(-1,-1),.2,colors.lightgrey),('LEFTPADDING',(0,0),(-1,-1),1.5*mm),('RIGHTPADDING',(0,0),(-1,-1),1.5*mm),('TOPPADDING',(0,0),(-1,-1),1.5*mm),('BOTTOMPADDING',(0,0),(-1,-1),1.5*mm)]))
        story += [t,Spacer(1,4*mm)]
    story += [PageBreak(),Paragraph('AUDIT — WHY IS THIS ITEM HERE?',h)]
    audit=[['TYPE','ITEM','SOURCE / OWNERSHIP','WIKI']]
    for x in sorted(items,key=lambda z:(z.kind,z.title.casefold())):audit.append([x.kind,x.title,x.acquisition or x.source or 'explicit',x.url])
    t=Table(audit,colWidths=[20*mm,50*mm,55*mm,55*mm],repeatRows=1);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.lightgrey),('GRID',(0,0),(-1,-1),.25,colors.grey),('FONTSIZE',(0,0),(-1,-1),5),('LEADING',(0,0),(-1,-1),6),('VALIGN',(0,0),(-1,-1),'TOP')]))
    story += [t,Spacer(1,4*mm),Paragraph(f'Source: https://helldivers.wiki.gg/wiki/ — {WIKI_LICENSE}. Helldivers and associated assets are property of their respective owners. Personal reference use.',tiny)]
    doc.build(story);return PDF_NAME
