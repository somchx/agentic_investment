import {useEffect,useRef,useState} from 'react'
import {useMutation,useQueryClient} from '@tanstack/react-query'
import {clarificationResult} from '@/api/thesis-clarification'
import {Loader2} from 'lucide-react'
import {apiClient,getApiErrorMessage} from '@/api/client'
import {Button} from '@/components/ui/button'
import {Textarea} from '@/components/ui/textarea'
import {Select} from '@/components/ui/select'
import {useTranslation} from '@/i18n/context'
import type {Reason,NaturalClaim} from '@/types'

type Question={key:string;text:string;why:string;options:{label:string;explanation:string}[]}
type Draft={id:string;revision:number;state:string;company:string;original_text:string;understood?:string;explanation?:string;question?:Question;answers:{question:Question;answer:string}[];claims:(NaturalClaim&{scope:string;timeframe:string;comparison_basis:string;evidence_standard:string})[];error?:string;limit_reached?:boolean;confirmation_token?:string;metrics:unknown[];processing_at?:number}
export function NaturalReasonForm({reason,onDone,ticker:companyTicker}:{reason?:Reason;onDone?:(key:string)=>void;ticker?:string}){
 const {lang}=useTranslation();const th=lang==='th';const cache=useQueryClient()
 const [ticker,setTicker]=useState(reason?.ticker||companyTicker||'AAPL');const [text,setText]=useState(reason?.original_text||'')
 const [draft,setDraft]=useState<Draft|null>(null);const [answer,setAnswer]=useState('');const [confirmed,setConfirmed]=useState(false)
 const request=useRef<AbortController|null>(null);const nextStep=useRef<HTMLElement|null>(null)
 const [elapsed,setElapsed]=useState(0)
 useEffect(()=>()=>{request.current?.abort()},[])
 function requestSignal(){request.current?.abort();request.current=new AbortController();return request.current.signal}
 function received(data:Draft){setDraft(data);setAnswer('');setConfirmed(false);requestAnimationFrame(()=>{nextStep.current?.focus({preventScroll:true});nextStep.current?.scrollIntoView({behavior:'smooth',block:'start'})})}
 const recover=useMutation({mutationFn:(current:Draft)=>clarificationResult(current,requestSignal()),onSuccess:received})
 const draftKey=`reasoncheck-clarification:${reason?.reason_key||ticker}`
 useEffect(()=>{
  const id=sessionStorage.getItem(draftKey);let active=true
  if(id)apiClient.get<Draft>(`/theses/clarifications/${id}`,{timeout:10000}).then(({data})=>{if(!active)return;if(['CONFIRMED','COMPLETED','INVESTIGATING'].includes(data.state)){sessionStorage.removeItem(draftKey);return}setDraft(data);setText(data.original_text);if(data.state==='PROCESSING')recover.mutate(data)}).catch(()=>{if(active)sessionStorage.removeItem(draftKey)})
  return ()=>{active=false}
 },[draftKey])
 useEffect(()=>{if(draft)sessionStorage.setItem(draftKey,draft.id)},[draft,draftKey])
 const act=useMutation({mutationFn:async({action,keep_answers}:{action:string;keep_answers?:number})=>{
  const signal=requestSignal()
  let current=draft
  if(!current){current=(await apiClient.post<Draft>('/theses/clarifications',{ticker,original_text:text},{timeout:15000,signal})).data;setDraft(current)}
  try{return await clarificationResult(current,signal,{revision:current.revision,action,answer,question_key:current.question?.key,keep_answers})}
  catch(error){if(signal.aborted)throw error;try{setDraft((await apiClient.get<Draft>(`/theses/clarifications/${current.id}`,{timeout:8000})).data)}catch{/* keep saved retry point */}throw error}
 },onSuccess:received})
 const save=useMutation({mutationFn:async()=> (await apiClient.post('/theses/confirm',{
  confirmation_token:draft?.confirmation_token,confirmed,reason_key:reason?.reason_key,
  expected_version_id:reason?.rule_definition?.thesis_version_id})).data,
  onSuccess:async data=>{sessionStorage.removeItem(draftKey);await cache.invalidateQueries({queryKey:['reasons']});await cache.invalidateQueries({queryKey:['report']});onDone?.(data.reason_key)}})
 const waiting=act.isPending||recover.isPending
 const busy=waiting||save.isPending
 const stale=draft?.state==='PROCESSING'&&Date.now()/1000-(draft.processing_at||Date.now()/1000)>=180
 const processing=draft?.state==='PROCESSING'&&!stale
 useEffect(()=>{if(!waiting){setElapsed(0);return}const start=Date.now();const timer=setInterval(()=>setElapsed(Math.floor((Date.now()-start)/1000)),1000);return()=>clearInterval(timer)},[waiting])
 const ready=draft?.state==='READY_FOR_CONFIRMATION'||draft?.state==='EXPLORATORY'
 function reset(){request.current?.abort();recover.reset();sessionStorage.removeItem(draftKey);setDraft(null);setConfirmed(false);setAnswer('');act.reset();save.reset()}
 return <div className="space-y-5">
  <h2 className="text-xl">{th?'เริ่มจากเหตุผลของคุณ แล้วช่วยกันทำให้ชัด':'Start with your reason. Let’s make it clear.'}</h2>
  <p className="text-sm text-muted-foreground">{th?'ขั้นนี้ถามให้เข้าใจก่อน ยังไม่ค้นเอกสารหรือสรุปผลบริษัท ใช้ AI แบบมีค่าใช้จ่าย สูงสุด 6 คำตอบและ 9 ครั้งเรียก AI ต่อร่าง':'We clarify first, before searching documents or judging the company. Paid AI is limited to 6 answers and 9 calls per draft.'}</p>
  <Select value={ticker} disabled={!!reason||!!companyTicker||busy||processing} onChange={v=>{setTicker(v);reset()}} options={['AAPL','MSFT','AMZN','GOOGL','NVDA'].map(value=>({value,label:value}))}/>
  <label className="block text-sm">{th?'เหตุผลต้นฉบับ':'Original thesis'}<Textarea aria-label="Original thesis" value={text} disabled={busy||processing} onChange={e=>{setText(e.target.value);reset()}} maxLength={5000} rows={4} placeholder={th?'ซื้อ Amazon เพราะคิดว่าน่าจะเติบโตดี':'I bought Amazon because I expect it to grow well.'}/></label>
  {!draft&&<Button type="button" disabled={text.trim().length<10||busy} onClick={()=>act.mutate({action:'retry'})}>{th?'ช่วยทำให้เหตุผลชัดเจน':'Clarify my reason'}</Button>}
  {draft&&<div className="space-y-4">
   {draft.answers.map((a,i)=><div key={i} className="rounded-lg border p-3 text-sm"><p className="text-muted-foreground">{a.question.text}</p><p>{a.answer}</p><Button type="button" variant="outline" disabled={busy||processing} onClick={()=>act.mutate({action:'rewind',keep_answers:i})}>{th?'แก้คำตอบนี้':'Revise this answer'}</Button></div>)}
   {draft.understood&&<p className="text-sm">{draft.understood}</p>}
   {draft.question&&!ready&&<section ref={nextStep} tabIndex={-1} className="scroll-mt-4 rounded-xl border bg-primary/5 p-5 space-y-3">
    <h3 className="font-semibold">{draft.question.text}</h3><p className="text-sm text-muted-foreground">{draft.question.why}</p>
    {draft.question.options.map(o=><label key={o.label} className="flex cursor-pointer gap-3 rounded-lg border bg-background p-3"><input type="radio" name="clarification-answer" checked={answer===o.label} disabled={busy||processing} onChange={()=>setAnswer(o.label)}/><span>{o.label}<small className="block text-muted-foreground">{o.explanation}</small></span></label>)}
    <label className="block text-sm">{th?'หรือเขียนคำตอบของคุณเอง':'Or answer in your own words'}<Textarea aria-label="Clarification answer" value={answer} disabled={busy||processing} maxLength={1000} onChange={e=>setAnswer(e.target.value)} rows={2}/></label>
    <div className="flex flex-wrap gap-2"><Button type="button" disabled={!answer.trim()||busy||processing} onClick={()=>act.mutate({action:'answer'})}>{waiting?<><Loader2 className="mr-2 h-4 w-4 animate-spin"/>{th?'กำลังเรียบเรียงคำถามถัดไป…':'Preparing the next step…'}</>:(th?'ส่งคำตอบ':'Continue')}</Button><Button type="button" variant="outline" disabled={busy||processing} onClick={()=>act.mutate({action:'explain'})}>{th?'ยังไม่แน่ใจ ช่วยอธิบายตัวเลือก':'Not sure — explain these choices'}</Button></div>
    {waiting&&<div role="status" aria-live="polite" className="flex items-start gap-3 rounded-lg border bg-background p-4 text-sm"><Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin"/><div><strong>{th?'กำลังอ่านคำตอบของคุณ':'Reading your answer'}</strong><p>{elapsed<20?(th?'AI กำลังเตรียมขั้นตอนถัดไป ไม่ต้องกดซ้ำหรือรีเฟรช':'AI is preparing the next step. No need to resubmit or refresh.'):(th?'ใช้เวลานานกว่าปกติ กำลังตรวจรับผลอัตโนมัติ โดยไม่ส่งคำตอบซ้ำ':'Taking longer than usual. Checking for the result without resubmitting.')}</p><span className="text-muted-foreground">{elapsed} {th?'วินาที':'seconds'}</span></div></div>}
   </section>}
   {draft.explanation&&<p className="rounded-lg border p-4 text-sm" role="status">{draft.explanation}</p>}
   {draft.limit_reached&&<p>{th?'ถึงจำนวนรอบถามที่กำหนดแล้ว คำตอบของคุณยังอยู่ ลองสรุปจากคำตอบเดิมได้':'The question limit was reached. Your answers are saved; try preparing the summary from them.'}</p>}
   {ready&&<section ref={nextStep} tabIndex={-1} className="scroll-mt-4 rounded-xl border bg-primary/5 p-5 space-y-4"><h3 className="font-semibold">{th?'เหตุผลที่คุณต้องการติดตาม — ตรวจให้ตรงใจก่อนบันทึก':'Your reason to monitor — review before saving'}</h3><p>{th?'บริษัท':'Company'}: {ticker}</p>
    {draft.state==='EXPLORATORY'&&<p>{th?'สำรวจข้อมูลก่อน: ยังไม่มีเกณฑ์ตัดสินว่าผ่านหรือไม่ผ่าน ระบบจะแสดงเฉพาะข้อมูลที่ตรวจได้และสิ่งที่ยังไม่แน่ใจ':'Exploration: no agreed success criterion. We will show verified observations and uncertainties without a pass/fail verdict.'}</p>}
    {draft.claims?.map(c=><article key={c.claim_id} className="space-y-2 text-sm"><strong>{c.expectation}</strong><p>{th?'สิ่งที่ติดตาม':'Scope'}: {c.scope}</p><p>{th?'ช่วงเวลา':'Timeframe'}: {c.timeframe}</p><p>{th?'เปรียบเทียบกับ':'Comparison'}: {c.comparison_basis}</p><p>{th?'ระบบจะตรวจสอบ':'We will check'}: {c.checkable_question}</p><p>{th?'หลักฐานที่ต้องใช้':'Evidence needed'}: {c.evidence_standard}</p></article>)}
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={confirmed} disabled={busy||processing} onChange={e=>setConfirmed(e.target.checked)}/>{th?'ความหมายนี้ตรงกับที่ฉันต้องการติดตาม':'This is the meaning I want to monitor'}</label>
    <Button type="button" disabled={!confirmed||busy} onClick={()=>save.mutate()}>{th?'ยืนยันและบันทึกเหตุผล':'Confirm and save reason'}</Button>
    <details className="text-sm"><summary>{th?'ดูคำอธิบายเพิ่มเติม':'Explain this preview'}</summary><p>{th?'สิ่งที่ติดตามคือเรื่องที่คุณอยากรู้ ช่วงเวลาระบุว่าจะดูงบงวดใด การเปรียบเทียบบอกว่าจะเทียบกับอะไร ส่วนหลักฐานคือข้อมูลที่ต้องพบก่อนสรุป หากไม่ตรงความตั้งใจ ให้แก้ก่อนยืนยัน':'Scope is what you want to track. Timeframe specifies which reporting periods to check; comparison states what to compare against. Evidence describes what must be found before concluding. Edit anything that does not match your intent.'}</p></details>
    <Button type="button" variant="outline" disabled={busy||processing} onClick={reset}>{th?'กลับไปแก้เหตุผล':'Edit my reason'}</Button>
    <p className="text-xs">{th?'การแก้ไขสร้างเวอร์ชันใหม่ เหตุผลที่บันทึกไว้ตอนซื้อยังคงเดิม หลังบันทึกคุณจึงเลือกเริ่มตรวจหลักฐานได้':'Edits create a new version and preserve purchase-time reasons. After saving, you can start evidence investigation.'}</p>
   </section>}
   {!ready&&!processing&&<div className="flex flex-wrap gap-2">
    {(stale||!draft.question||draft.error||act.isError)&&(!draft.limit_reached||draft.error)&&<Button type="button" variant="outline" disabled={busy||processing} onClick={()=>act.mutate({action:'retry'})}>{th?'สรุปจากคำตอบเดิม':'Summarize saved answers'}</Button>}
    <Button type="button" variant="outline" disabled={busy||processing} onClick={()=>act.mutate({action:'explore'})}>{th?'สำรวจข้อมูลก่อน ยังไม่ตั้งเกณฑ์':'Explore first, without a success criterion'}</Button>
   </div>}
   <details className="text-xs"><summary>{th?'รายละเอียดสำหรับผู้วิจัย':'Technical details'}</summary><pre className="overflow-auto">{JSON.stringify({state:draft.state,revision:draft.revision,metrics:draft.metrics},null,2)}</pre></details>
  </div>}
  {waiting&&!draft?.question&&<p role="status" className="flex items-center gap-2"><Loader2 className="h-5 w-5 animate-spin"/>{th?'กำลังเตรียมขั้นตอนถัดไป ไม่ต้องรีเฟรช':'Preparing the next step — no refresh needed'} · {elapsed}s</p>}
  {draft?.state==='PROCESSING'&&!waiting&&<Button type="button" variant="outline" onClick={()=>{act.reset();recover.mutate(draft)}}>{th?'ตรวจรับผลคำตอบที่ส่งแล้ว':'Check the submitted answer'}</Button>}
  {(act.isError||recover.isError||save.isError||draft?.error)&&<p role="alert" className="text-sm text-destructive">{draft?.error?(th?'ระบบจัดทำสรุปไม่สำเร็จ คำตอบของคุณยังอยู่ กดสรุปจากคำตอบเดิมได้โดยไม่ต้องตอบใหม่':'The system could not prepare the summary. Your answers are saved; summarize them without starting over.'):getApiErrorMessage(act.error||recover.error||save.error,th?'การเชื่อมต่อใช้เวลานาน ตรวจรับผลที่บันทึกไว้ได้โดยไม่ต้องรีเฟรช':'Connection delayed. Check the saved result without refreshing.')}</p>}
 </div>
}
