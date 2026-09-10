"""Download explicitly selected Commons architectural photographs to external storage."""
import urllib.request, urllib.parse, urllib.error, json, pathlib, hashlib, re, time
ROOT=pathlib.Path(__file__).resolve().parents[1]
SELECTION={
'bund-18':'Chartered Bank Building, Shanghai 20250501.jpg',
'aia-building':'North China Daily News Building 20250501.jpg',
'russo-chinese-bank':'Russo-Chinese Bank Building, Shanghai.JPG',
'customs-house':'Customs House, Shanghai 20250501-1.jpg',
'hsbc-bund':'HSBC Building, Shanghai 20250501-1.jpg',
'bank-china':'Bank of China Building, Shanghai 20250501.jpg',
'pearl-base':'Base of Oriental Pearl Tower.jpg',
'peace-hotel':'Sassoon House 20250501.jpg',
'palace-hotel':'Shanghai Palace Hotel 20250501.jpg',
'customs-full':'Customs House, Shanghai 20250501-2.jpg',
'asia-building':'Asia Building, Shanghai 20250501.jpg',
'bank-taiwan':'Bank of Taiwan Building, Shanghai 20250501.jpg',
'bank-communications':'Bank of Communications Building, Shanghai 20250501.jpg',
'china-merchants':'China Merchants Building, Shanghai 20250501.jpg',
'super-brand-mall':'Shanghai, 29 June 2024 (53).jpg',
'super-brand-exterior':'正大广场白天外景.jpg',
'ocean-aquarium':'Shanghai Ocean Aquarium.jpg',
'hang-seng':'Hang Seng Bank Tower.jpg',
'bea-tower':'BEA Finance Tower.jpg',
'ping-an':'DSC00262中国平安大楼.jpg',
}
def api(params):
 u='https://commons.wikimedia.org/w/api.php?'+urllib.parse.urlencode({'action':'query','format':'json',**params})
 req=urllib.request.Request(u,headers={'User-Agent':'ShanghaiSightseeingReference/1.0 (local architecture study)'})
 for retry in range(4):
  try:return json.load(urllib.request.urlopen(req,timeout=30))
  except urllib.error.HTTPError as e:
   if e.code!=429 or retry==3:raise
   time.sleep(30*(retry+1))
def main():
 report=ROOT/'references/tourism/architecture-photos.json'
 records=json.loads(report.read_text()) if report.exists() else []
 for key,title in SELECTION.items():
  if any(r['id']==key and (ROOT/r['file']).exists() for r in records):continue
  dst=ROOT/'assets/streets/references'/f'{key}.jpg'
  j=api({'titles':'File:'+title,'prop':'imageinfo','iiprop':'url|extmetadata','iiurlwidth':'1920'})
  info=next(iter(j['query']['pages'].values()))['imageinfo'][0];meta=info['extmetadata'];license=meta['LicenseShortName']['value']
  assert license in ['CC0','CC BY-SA 4.0','CC BY-SA 3.0','CC BY-SA 2.5','CC BY 4.0','CC BY 3.0','CC BY 2.0','Public domain'],license
  url=info.get('thumburl',info['url']).split('?')[0]
  if not dst.exists():
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ShanghaiSightseeingReference/1.0'}),timeout=60) as s:data=s.read()
   assert data[:2]==b'\xff\xd8';dst.write_bytes(data)
  records.append({'id':key,'title':title,'file':str(dst.relative_to(ROOT)),'source':info['descriptionurl'],'download':url,'author':re.sub('<[^>]+>','',meta['Artist']['value']),'license':license,'licenseUrl':meta.get('LicenseUrl',{}).get('value'),'date':meta.get('DateTimeOriginal',{}).get('value'),'bytes':dst.stat().st_size,'sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'usage':'exterior-reference'})
  print(key,license,dst.stat().st_size,flush=True)
  report.write_text(json.dumps(records,ensure_ascii=False,indent=2))
  time.sleep(3)

if __name__=='__main__': main()
