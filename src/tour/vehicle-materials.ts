import * as THREE from 'three';

/** Exterior-only vehicles use alpha glass and environment reflections.
 * Screen-space refraction would render the whole city again for a lamp cover.
 * Original downloaded materials and textures stay intact on disk.
 */
export function prepareVehicleMaterials(model:THREE.Object3D,carId?:string) {
  const handled=new Set<THREE.Material>();
  model.traverse(object=>{
    if(!(object instanceof THREE.Mesh))return;
    for(const material of Array.isArray(object.material)?object.material:[object.material]){
      if(handled.has(material))continue;handled.add(material);
      if(carId==='alphard' && material instanceof THREE.MeshPhysicalMaterial){
        // The source's bright tire diffuse/specular values looked white in daylight.
        if(material.name==='tire.139'){
          material.color.set('#18191b');material.metalness=0;material.roughness=.86;
          material.specularColor.set('#ffffff');material.specularIntensity=.25;
        }
        // Cabin-only glass is separate from the original clear/red/orange lamp covers.
        if(material.name==='windowglass.139'||material.name==='darkglass.010'){
          material.color.set('#172125');material.opacity=1;material.transparent=false;
          material.depthWrite=true;material.roughness=.16;material.transmission=0;
          material.specularColor.set('#ffffff');material.needsUpdate=true;
        }
      }
      if(!(material instanceof THREE.MeshPhysicalMaterial)||material.transmission<=0)continue;
      const transmission=material.transmission;
      material.transmission=0;
      // A fully opaque clear lamp shell still needs to expose the lamp beneath.
      if(!material.transparent){material.transparent=true;material.opacity=Math.min(material.opacity,1-transmission*.85);material.depthWrite=false;}
      material.needsUpdate=true;
    }
  });
}
