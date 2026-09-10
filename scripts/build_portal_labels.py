"""Render original road-sign lettering; never edit or embed reference photos."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib, json, shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/streets/tunnel-portals/labels/r1'
PUBLIC=ROOT/'public/streets/textures'
OUT.mkdir(parents=True,exist_ok=True)
font='/System/Library/Fonts/PingFang.ttc'
if not Path(font).exists():font='/System/Library/Fonts/Supplemental/Songti.ttc'
def face(size):return ImageFont.truetype(font,size,index=0 if 'PingFang' in font else 6)
labels=[('renmin','人民路隧道','RENMIN ROAD TUNNEL'),('xinjian','新建路隧道','XINJIAN ROAD TUNNEL'),('hailun','新建路隧道','XINJIAN ROAD TUNNEL'),('limit43','4.3m','')]
records=[]
for key,title,english in labels:
    image=Image.new('RGBA',(2048,512),(22,71,140,255) if key!='hailun' else (0,0,0,0))
    draw=ImageDraw.Draw(image)
    color=(248,246,227,255) if key!='hailun' else (171,35,28,255)
    draw.text((1024,155),title,font=face(188),anchor='mm',fill=color,stroke_width=1)
    draw.text((1024,374),english,font=face(78),anchor='mm',fill=(246,231,170,255))
    if key=='limit43':
        image=Image.new('RGBA',(512,512),(0,0,0,0));draw=ImageDraw.Draw(image)
        draw.ellipse((14,14,498,498),fill=(244,242,225,255),outline=(161,37,31,255),width=42)
        draw.text((256,258),'4.3m',font=face(147),anchor='mm',fill=(34,40,37,255))
    target=OUT/(key+'.png')
    if not target.exists():image.save(target)
    published=PUBLIC/('portal-'+key+'-r1.png');shutil.copy2(target,published)
    assert target.read_bytes()==published.read_bytes()
    records.append({'id':key,'original':str(target.relative_to(ROOT)),'runtime':str(published.relative_to(ROOT)),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'text':title,'sourcePixelsUsed':False})
(OUT/'labels.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'labels':len(records),'originalsPreserved':True}))
