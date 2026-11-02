import {useState} from 'react'
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {apiClient,getApiErrorMessage} from '@/api/client'
import {Button} from '@/components/ui/button'
import {Input} from '@/components/ui/input'
import {useTranslation} from '@/i18n/context'
import type {RuleDefinition,NaturalInvestigation,NaturalObservation} from '@/types'

function statusText(status:string,th:boolean){
 return ({SUFFICIENT:th?'มีหลักฐานเพียงพอสำหรับประเด็นที่ตรวจ':'Enough evidence for the reviewed question',CONFLICTING:th?'พบหลักฐานที่ขัดแย้งกัน ต้องตรวจต่อ':'Evidence conflicts and needs further review',NOT_YET_OBSERVABLE:th?'ข้อมูลยังไม่เผยแพร่ ณ วันที่ประเมิน':'Information was not available as of this date',INSUFFICIENT:th?'หลักฐานยังไม่พอที่จะสรุป':'Not enough evidence to conclude'} as Record<string,string>)[status] || (th?'ยังต้องตรวจสอบ':'Needs review')
}
function Evidence({items}:{items:NaturalObservation[]}){
 return <div className="space-y-2">{items.map((o,i)=><blockquote key={i} className="rounded-r-lg border-l-2 border-primary bg-primary/5 p-3 text-sm">
  <p>{o.statement}</p><p className="text-xs text-muted-foreground">“{o.quote}”</p>
  <a className="text-xs underline" href={o.source.source_url} target="_blank" rel="noreferrer">{o.source.form} · {o.source.period_end} · {o.source.filed}</a>
 </blockquote>)}</div>
}
export function NaturalInvestigationPanel({reasonKey,definition,purchaseId}:{reasonKey:string;definition:RuleDefinition;purchaseId?:number}){
 const {lang}=useTranslation();const th=lang==='th';const cache=useQueryClient()
 const needsClarification=definition.thesis_clarity==='NEEDS_CLARIFICATION'||(!definition.thesis_clarity&&definition.confirmed_interpretation?.claims.some(c=>c.ambiguities.length))
 const today=new Date().toISOString().slice(0,10)
 const [start,setStart]=useState('');const [end,setEnd]=useState('');const [asOf,setAsOf]=useState(today);const [cost,setCost]=useState(false)
 const key=['natural-investigations',reasonKey,definition.thesis_version_id,purchaseId]
 const runs=useQuery<{id:string;created_at:string;result:NaturalInvestigation}[]>({queryKey:key,queryFn:async()=> (await apiClient.get(`/theses/${reasonKey}/investigations`,{params:{thesis_version_id:definition.thesis_version_id,purchase_id:purchaseId}})).data})
 const versions=useQuery<{id:string;version_no:number;original_text:string}[]>({queryKey:['thesis-versions',reasonKey],queryFn:async()=> (await apiClient.get(`/theses/${reasonKey}/versions`)).data})
 const [selected,setSelected]=useState<string|null>(null)
 const run=useMutation({mutationFn:async()=> (await apiClient.post(`/theses/${reasonKey}/investigate`,{
  thesis_version_id:definition.thesis_version_id,purchase_id:purchaseId,evaluation_date:asOf,period_start:start,period_end:end,acknowledge_cost:cost})).data,
  onSuccess:async()=>{setSelected(null);await cache.invalidateQueries({queryKey:key})}})
 const records=runs.data||[];const result=records.find(r=>r.id===selected)?.result||records[0]?.result
 return <div className="space-y-5 text-sm">
  <h3 className="font-semibold">{th?'ตรวจหลักฐานเหตุผลการลงทุน':'Thesis evidence investigation'} · v{definition.version_no}</h3>
  <p>{definition.preview}</p><p className="text-xs">{th?'ตรวจหลักฐานทางธุรกิจ ไม่ใช่ผลผ่าน/ไม่ผ่านเกณฑ์ตัวเลข':'Business evidence assessment, not a numerical pass/fail verdict'}</p>
  {needsClarification&&<p role="alert" className="rounded border p-3">{th?'เหตุผลเวอร์ชันนี้ยังไม่ชัด กรุณาแก้เหตุผลในหน้าคัดกรองและยืนยันความหมายใหม่ก่อนตรวจหลักฐาน เหตุผลเดิมตอนซื้อจะยังคงอยู่':'This version needs clarification. Edit the reason in Screener and confirm its meaning before investigating. Existing purchase snapshots remain unchanged.'}</p>}
  {definition.thesis_clarity==='EXPLORATORY'&&<p>{th?'โหมดสำรวจ: ยังไม่ได้ตกลงเกณฑ์ความสำเร็จ จึงไม่ตัดสินว่าบริษัททำได้ตามที่คาดหวัง':'Exploration: no agreed success criterion, so this cannot decide whether the company meets your expectations.'}</p>}
  {definition.confirmed_interpretation?.claims.map(c=><div key={c.claim_id} className="rounded-xl border bg-primary/5 p-4"><strong>{c.expectation}</strong><p>{c.checkable_question}</p>{c.user_clarification&&<p>{c.user_clarification}</p>}</div>)}
  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
   <label>{th?'งวดรายงานตั้งแต่':'Reporting window from'}<Input aria-label="Period start" type="date" value={start} max={end||asOf} onChange={e=>setStart(e.target.value)}/></label>
   <label>{th?'ถึง':'Through'}<Input aria-label="Period end" type="date" value={end} max={asOf} min={start} onChange={e=>setEnd(e.target.value)}/></label>
   <label>{th?'ประเมิน ณ วันที่':'As of'}<Input aria-label="Evaluation date" type="date" value={asOf} max={today} onChange={e=>setAsOf(e.target.value)}/></label>
  </div>
  <p className="text-xs text-muted-foreground">{th?'ค้นเอกสารที่วันสิ้นงวดอยู่ในช่วงที่เลือก ใช้ได้หลังวันยื่น 1 วัน ตรวจซ้ำยึดเวอร์ชันเดิม ไม่ตีความใหม่':'Uses filings with reporting dates in this window, available one day after filing. Rechecks preserve the confirmed version.'}</p>
  <label className="flex gap-2"><input type="checkbox" checked={cost} onChange={e=>setCost(e.target.checked)}/>{th?'ยอมรับค่า LLM: สูงสุด 6 รอบสืบค้นและ 4 ครั้งตรวจหลักฐาน':'Accept LLM cost: up to 6 planner rounds and 4 verification calls'}</label>
  <Button type="button" disabled={needsClarification||!cost||!start||!end||start>end||end>asOf||asOf>today||run.isPending} onClick={()=>run.mutate()}>{run.isPending?(th?'กำลังสืบค้นและตรวจหลักฐาน…':'Investigating…'):(th?'ตรวจหลักฐาน / ตรวจซ้ำ':'Investigate / recheck')}</Button>
  {(run.isError||runs.isError)&&<p role="alert" className="text-destructive">{getApiErrorMessage(run.error||runs.error)}</p>}
  {!!records.length&&<label className="block">{th?'ประวัติการตรวจเวอร์ชันนี้':'Investigation timeline for this version'}<select className="block w-full rounded border bg-[var(--bg-input)] p-2" value={selected||records[0].id} onChange={e=>setSelected(e.target.value)}>{records.map(r=><option key={r.id} value={r.id}>{r.result.evaluation_date} · {statusText(r.result.evidence_status,th)} · {r.created_at}</option>)}</select></label>}
  {result&&<div className="space-y-4">
   <h3 className="font-semibold">{th?'ผลการตรวจสอบเหตุผลการลงทุน':'Investment reason review'}</h3><p>{statusText(result.evidence_status,th)}</p>{result.evidence_status==='INSUFFICIENT'&&<p>{th?'ระบบยังยืนยันไม่ได้ว่าบริษัทเป็นไปตามที่คุณคาดหวัง เพราะหลักฐานที่ตรวจได้ยังไม่เพียงพอ ไม่ได้หมายความว่าบริษัทไม่เติบโตหรือเหตุผลของคุณผิด':'We cannot yet confirm that the company meets your expectations. Too little verified evidence does not mean the company is failing or your reason is wrong.'}</p>}<p className="text-xs">{result.period_start} → {result.period_end} · As of {result.evaluation_date}</p>
   {result.claims.map(c=><details key={c.claim_id} className="rounded-xl border bg-[var(--bg-card)] p-5 space-y-3"><summary>{definition.confirmed_interpretation?.claims.find(claim=>claim.claim_id===c.claim_id)?.expectation|| (th?'ประเด็นที่ตรวจ':'Reviewed question')}: {statusText(c.evidence_status,th)}</summary><p>{th?'หลักฐานสนับสนุน':'Supporting evidence'}</p><Evidence items={c.supporting_evidence}/><p>{th?'หลักฐานขัดแย้ง':'Contradicting evidence'}</p><Evidence items={c.contradicting_evidence}/></details>)}
   <h4 className="font-semibold">{th?'1. สิ่งที่ตรวจสอบได้แล้ว':'1. What we have verified'}</h4><Evidence items={result.what_we_know}/>{!result.what_we_know.length&&<p>{th?'ยังไม่มีข้อเท็จจริงที่ผ่านการตรวจ':'No verified observations yet'}</p>}
   <h4 className="font-semibold">{th?'2. สิ่งที่ยังไม่แน่ใจ':'2. What remains uncertain'}</h4>{result.what_is_uncertain.map((u,i)=><p key={i}>{u.status&&statusText(u.status,th)} {u.question} {u.ambiguity}</p>)}
   <h4 className="font-semibold">{th?'3. สิ่งที่ควรตรวจสอบต่อ':'3. What to investigate next'}</h4>{result.what_to_investigate_next.map((n,i)=><p key={i}>{(n.follow_up_questions?.length ? n.follow_up_questions : [n.question]).join(' · ')}<span className="block text-xs text-muted-foreground">{th?'ตรวจจากรายงาน 10-Q / 10-K และหมายเหตุที่เกี่ยวข้อง เพื่อเติมหลักฐานที่ยังขาดหรือยืนยันข้อขัดแย้ง':'Review relevant 10-Q / 10-K reports and notes to fill evidence gaps or resolve contradictions.'}</span></p>)}
   <p className="text-xs">{th?'ค้นเฉพาะเอกสาร SEC ในขอบเขตที่เลือกและภายในจำนวนครั้งที่จำกัด การตรวจความหมายใช้ AI และยังต้องให้มนุษย์ทบทวน':'Search covers selected SEC filings within a bounded budget. AI evidence interpretation still needs human review.'}</p><details><summary>{th?'รายละเอียดเชิงเทคนิค / สำหรับผู้วิจัย':'Advanced / technical details'}</summary><pre className="max-h-96 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(result,null,2)}</pre></details>
  </div>}
  <details><summary>{th?'ประวัติเวอร์ชันเหตุผล':'Thesis version history'}</summary>{versions.data?.map(v=><p key={v.id}>v{v.version_no} · {v.original_text}</p>)}</details>
 </div>
}
