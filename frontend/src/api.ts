export const BASE='/api/second_brain';
export async function api(path:string,method='GET',data?:unknown):Promise<any>{
 const csrf=document.cookie.split('; ').find(x=>x.startsWith('csrftoken='))?.split('=')[1]||'';
 const form=data instanceof FormData;
 const response=await fetch(BASE+path,{method,credentials:'same-origin',headers:{...(method!=='GET'?{'X-CSRFToken':decodeURIComponent(csrf)}:{}),...(!form&&data?{'Content-Type':'application/json'}:{})},body:data?(form?data:JSON.stringify(data)):undefined});
 if(!response.ok){let message='Request failed. Please try again.';try{message=(await response.json()).error||message}catch{}throw new Error(message)}
 return response.json();
}
export async function download(path:string,name:string){const r=await fetch(BASE+path,{credentials:'same-origin'});if(!r.ok)throw new Error((await r.json()).error);const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
