const database=()=>new Promise<IDBDatabase>((resolve,reject)=>{
  const request=indexedDB.open('shanghai-tour-album',1);
  request.onupgradeneeded=()=>request.result.createObjectStore('photos',{keyPath:'id'});
  request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
});
export async function storePhoto(id:string,name:string,blob:Blob){
  const db=await database();
  try{await new Promise<void>((resolve,reject)=>{const tx=db.transaction('photos','readwrite');tx.objectStore('photos').put({id,name,blob,capturedAt:new Date().toISOString()});tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});}finally{db.close();}
}
export async function readPhotos():Promise<{id:string;name:string;blob:Blob;capturedAt:string}[]>{
  const db=await database();
  try{return await new Promise((resolve,reject)=>{const request=db.transaction('photos').objectStore('photos').getAll();request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});}finally{db.close();}
}
