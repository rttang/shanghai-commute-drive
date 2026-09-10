"""Publish attribution alongside the combined street scene, keeping provenance."""
import html
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public/streets'
base = json.loads((PUBLIC / 'credits.json').read_text())
base = [r for r in base if r.get('collection') != 'street-master-expansion']
photos = json.loads((ROOT / 'references/tourism/streets-expansion-photos.json').read_text())
generated = json.loads((ROOT / 'docs/evidence/tourism/street-master-generated-images.json').read_text())
generated_ids = {r['sourceReferenceId'] for r in generated}
extra = []
for p in photos:
    if not p['visualInspection']['accepted']:
        continue
    r = {key:p.get(key) for key in ('id','title','source','author','license','licenseUrl','date','sha256','wayIds')}
    r['collection'] = 'street-master-expansion'
    r['modifications'] = ('内置 image_gen 校正透视与补全遮挡，Blender 按校正图制作独立窗洞、柱廊及屋顶。' if p['id'] in generated_ids else '依据照片观察外观、颜色和可见结构，Blender 重建；部分细节使用原照片映射。') + '未见侧面、遮挡区域及无实测尺寸的细节为推断，非摄影测量。'
    r['observationScope'] = p['visualInspection']['observations']
    extra.append(r)
credits = base + extra
(PUBLIC / 'credits.json').write_text(json.dumps(credits,ensure_ascii=False,indent=2)+'\n')
esc = lambda value:html.escape(str(value or '未提供'),quote=True)
items = []
for r in credits:
    items.append(f'<li><a href="{esc(r["source"])}">{esc(r["title"])}</a> · {esc(r["author"])} · <a href="{esc(r["licenseUrl"])}">{esc(r["license"])}</a><p>{esc(r["modifications"])}</p></li>')
(PUBLIC / 'credits.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>上海街景照片来源</title><style>body{max-width:850px;margin:40px auto;padding:0 24px;color:#263d35;background:#f3f1e8;font:16px/1.8 system-ui}h1{font-family:"Songti SC",serif}li{margin-bottom:20px}a{color:#29594a}p{font-size:14px}</style><h1>街景照片与模型来源</h1><p>照片用于参考重建，不是实时街景或实测复原。不同拍摄日期的店铺与标识可能不同。可编辑工程和总模型保留各部分的作者、来源及派生许可；被排除的内景、施工期和反射重复照片仍保存在项目参考目录。</p><ul>'+''.join(items)+'</ul><p><a href="/">返回上海漫游</a></p></html>\n')
(PUBLIC / 'master/reference-catalog.json').write_text(json.dumps({'version':1,'photos':photos,'generatedTextures':[{k:v for k,v in r.items() if k not in ('path','retained')} for r in generated],'attribution':'/streets/credits.html','limits':'Photographic references and inferred reconstruction; not a measured or current street survey.'},ensure_ascii=False,indent=2)+'\n')
notices = ROOT / 'THIRD_PARTY_NOTICES.md'
marker = '\n## 2026-09-09 完整街景新增照片与派生模型\n'
text = notices.read_text().split(marker)[0]
rows = ['| 照片 | 作者 | 许可 |','| --- | --- | --- |']
for r in extra:
    rows.append(f'| [{r["title"]}]({r["source"]}) | {r["author"]} | [{r["license"]}]({r["licenseUrl"]}) |')
text += marker+'\n本轮新增37张参考照片，34张用于外观参考、3张因室内、施工期或反射重复而排除但完整保留。逐照片原文件、日期、观察范围及SHA见 `references/tourism/streets-expansion-photos.json`。\n\n'+'\n'.join(rows)+'\n\n本轮校正立面由内置 image_gen 生成，源图、生成原件和移动硬盘副本均保留；提示集合位于 `references/tourism/generated-facade-instructions.json`，保存记录位于 `docs/evidence/tourism/street-master-generated-images.json`。独立窗洞、柱廊、屋顶、细部分体和摄影纹理一并纳入总模型。无照片的侧面、遮挡补全、部分层高与细节明确为推断。总GLB、分块及完整Blender工程为多个许可资产的集合，各组件继续遵守所列CC BY与CC BY-SA条款，包含上一轮俄华道胜、正大广场、恒生、东亚及水族馆的派生许可。地图沿用OpenStreetMap ODbL，不表示摄影者或建筑业主背书。\n'
notices.write_text(text)
print(json.dumps({'publishedCredits':len(credits),'newUsablePhotos':len(extra),'preservedReferencePhotos':len(photos)},ensure_ascii=False))
