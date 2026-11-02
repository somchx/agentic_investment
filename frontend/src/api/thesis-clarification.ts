import {isAxiosError} from 'axios'
import {apiClient} from './client'

/** Poll only reads: losing the POST response must not spend on another LLM call. */
export async function clarificationResult<T extends {id:string;revision:number;state:string}>(
 current:T, signal:AbortSignal, body?:Record<string,unknown>,
):Promise<T>{
 const controller=new AbortController()
 const abort=()=>controller.abort()
 signal.addEventListener('abort',abort,{once:true})
 if(signal.aborted)controller.abort()
 let postError:unknown
 const pause=()=>new Promise<void>((resolve,reject)=>{
  const stop=()=>{clearTimeout(timer);reject(new Error('Cancelled'))}
  const timer=setTimeout(()=>{controller.signal.removeEventListener('abort',stop);resolve()},1500)
  if(controller.signal.aborted)stop()
  else controller.signal.addEventListener('abort',stop,{once:true})
 })
 const posted=body ? apiClient.post<T>(`/theses/clarifications/${current.id}`,body,{signal:controller.signal,timeout:65000})
  .then(r=>r.data).catch(error=>{postError=error;return new Promise<T>(()=>{})}) : null
 const poll=async()=>{
  const deadline=Date.now()+90000
  while(Date.now()<deadline&&!controller.signal.aborted){
   await pause()
   let latest:T
   try{latest=(await apiClient.get<T>(`/theses/clarifications/${current.id}`,{signal:controller.signal,timeout:8000})).data}
   catch(error){if(controller.signal.aborted||(isAxiosError(error)&&[401,403,404].includes(error.response?.status||0)))throw error;continue}
   if(latest.state!=='PROCESSING'&&(!body||latest.revision>current.revision))return latest
   if(postError&&latest.state!=='PROCESSING')throw postError
  }
  throw new Error('The connection is taking too long. Check the saved answer again; do not resubmit it.')
 }
 try{return await (posted ? Promise.race([posted,poll()]) : poll())}
 finally{controller.abort();signal.removeEventListener('abort',abort)}
}
