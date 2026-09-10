// Publish only independently verified, already exported luxury assets into the active fleet.
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
const read=p=>JSON.parse(readFileSync(p,'utf8'));
const write=(p,data)=>writeFileSync(p,JSON.stringify(data,null,2)+'\n');
const order=['g63','urus','porsche-911','ferrari-488','alphard'];
const catalog={
  g63:{name:'奔驰 AMG G 63',category:'豪华越野 SUV',model:'2020 G 63 外观',color:'#3b3e42',tire:'275/50 R20'},
  urus:{name:'兰博基尼 Urus',category:'高性能 SUV',model:'2018 Urus 外观',color:'#d8b23a',tire:'285/45 R21'},
  'porsche-911':{name:'保时捷 911 Turbo S',category:'豪华跑车',model:'2020 992.1 Turbo S 外观',color:'#9a9eab',tire:'255/35 R20'},
  'ferrari-488':{name:'法拉利 488 GTB',category:'中置引擎跑车',model:'2015–2019 488 GTB 外观',color:'#b72d24',tire:'245/35 R20'},
  alphard:{name:'丰田 埃尔法',category:'豪华 MPV',model:'2015 第三代 Alphard 外观',color:'#ece9e0',tire:'235/50 R18'},
};
const fragment=read('references/luxury-fleet-ready.json');
const cars=read('src/tour/cars.json'), assets=read('src/tour/vehicle-assets.json');
const rigged=read('public/vehicles/rigged/manifest.json');
for(const id of order){
  const model=fragment.models.find(m=>m.id===id);if(!model)continue;
  for(const [file,expected] of [[model.file,model.runtimeSha256],[model.trafficFile,model.traffic.sha256]]){
    const bytes=readFileSync('public'+file);
    if(bytes.toString('ascii',0,4)!=='glTF'||bytes.readUInt32LE(8)!==bytes.length)throw Error(`Invalid GLB ${file}`);
    if(createHash('sha256').update(bytes).digest('hex')!==expected)throw Error(`SHA mismatch ${file}`);
  }
  if(!model.rigValidation.fourIndependentRolls||!model.rigValidation.frontSteerOnly||!model.rigValidation.bodyStationary)throw Error(`Unverified rig ${id}`);
  const car={id,...catalog[id],source:model.sourceUrl,gallery:model.sourceUrl,
    dimensions:model.nominalDimensionsM.map(n=>Math.round(n*1000)),wheelbase:Math.round(model.nominalWheelbaseM*1000),
    collisionDimensions:model.dimensionsM.map(n=>Math.round(n*1000))};
  const index=cars.findIndex(c=>c.id===id);if(index<0)cars.push(car);else cars[index]=car;
  assets[id]={file:model.file,trafficFile:model.trafficFile,preview:model.preview,displayModel:catalog[id].model,
    sourceYear:model.sourceYear,author:model.author,license:model.license,licenseUrl:model.licenseUrl,source:model.sourceUrl,
    status:'exterior-review',quality:`/vehicles/rigged/${id}-quality.json`};
  rigged.models=rigged.models.filter(m=>(m.id??m.car)!==id);rigged.models.push(model);
}
const retained=cars.filter(c=>!order.includes(c.id));
write('src/tour/cars.json',[...retained,...order.flatMap(id=>cars.filter(c=>c.id===id))]);
write('src/tour/vehicle-assets.json',assets);write('public/vehicles/rigged/manifest.json',rigged);
console.log(JSON.stringify({published:order.filter(id=>assets[id]),activeCount:cars.length}));
