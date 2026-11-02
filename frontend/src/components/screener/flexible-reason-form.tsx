import { TrendingUp, ChartNoAxesCombined, Landmark, SlidersHorizontal, ShieldCheck, Sparkles, CheckCircle2 } from 'lucide-react'
import { NaturalReasonForm } from '@/components/theses/natural-reason-form'
import { FinancialTagInfo, FinancialDataOrigin } from './financial-data-info'
import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient, getApiErrorMessage } from '@/api/client'
import { fetchAllXbrlTags } from '@/api/reasons'
import { useTranslation } from '@/i18n/context'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import type { Reason, ComparisonOp, ReasonKind } from '@/types'

const presets = [
  ['Revenue', 'revenue_non_decreasing', 'รายได้ไม่ลดลงจากงวดเดียวกันปีก่อน', 'Revenue does not decrease YoY', 'Revenue current ≥ prior-year comparable'],
  ['Revenue', 'revenue_increasing', 'รายได้เพิ่มขึ้นจากงวดเดียวกันปีก่อน', 'Revenue increases YoY', 'Revenue current > prior-year comparable'],
  ['Profitability', 'margin_non_decreasing', 'อัตรากำไรจากการดำเนินงานไม่ลดลง', 'Operating margin does not decrease YoY', '(Operating income / Revenue) current ≥ prior-year comparable'],
  ['Profitability', 'operating_profit_positive', 'ยังมีกำไรจากการดำเนินงาน', 'Operating income is positive', 'Operating income > 0 USD'],
  ['Debt', 'debt_non_increasing', 'หนี้ระยะยาวไม่เพิ่มจากงวดเดียวกันปีก่อน', 'Noncurrent debt does not increase YoY', 'Noncurrent long-term debt current ≤ prior-year comparable'],
]
function StructuredReasonForm({ reason, onDone, onNatural, ticker }: {reason?: Reason; onDone?: (key: string) => void; onNatural?:()=>void; ticker?:string}) {
  const {lang, tXbrlTag} = useTranslation(); const th=lang==='th'; const q=useQueryClient()
  const initial=reason?.rule_definition?.preset ?? (reason ? 'custom' : 'revenue_non_decreasing')
  const [preset,setPreset]=useState(initial)
  const [topic,setTopic]=useState(presets.find(p=>p[1]===initial)?.[0] ?? 'Custom')
  const [period,setPeriod]=useState(reason?.rule_definition?.evaluation_period ?? 'quarterly')
  const [original,setOriginal]=useState(reason?.original_text ?? '')
  const [description,setDescription]=useState(reason?.description ?? '')
  const [metric,setMetric]=useState(reason?.metric ?? '')
  const [den,setDen]=useState(reason?.denominator_metric ?? '')
  const [kind,setKind]=useState<ReasonKind>(reason?.kind ?? 'yoy_growth')
  const [op,setOp]=useState<ComparisonOp>(reason?.comparison ?? '>=')
  const [threshold,setThreshold]=useState(reason?.threshold != null ? String(reason.threshold*100) : '')
  const [confirmed,setConfirmed]=useState(false)
  const tags=useQuery({queryKey:['xbrl-tags','__all__'],queryFn:fetchAllXbrlTags,enabled:preset==='custom',staleTime:300000})
  const selected=presets.find(p=>p[1]===preset)
  const preview=preset==='custom' ? `${metric || '…'}${kind==='margin_level' ? ` / ${den || '…'}` : ' YoY'} ${op} ${threshold || '…'}%` : selected?.[4] ?? ''
  const label=selected?.[th?2:3] ?? description
  const options=(tags.data ?? []).map(t=>({value:t.tag,label:tXbrlTag(t.tag,t.label,t.label_th)}))
  if(metric && !options.some(o=>o.value===metric)) options.unshift({value:metric,label:metric})
  if(den && !options.some(o=>o.value===den)) options.push({value:den,label:den})
  const mutation=useMutation({mutationFn:async()=>{
    const payload={reason_key:reason?.reason_key ?? `custom_${crypto.randomUUID()}`, ticker:reason?.ticker ?? ticker ?? null,
      preview_ticker:reason?.ticker || ticker || 'AAPL', description:label.trim(), original_text:original,
      metric,kind,comparison:op,threshold:preset==='custom'?Number(threshold)/100:null,
      denominator_metric:kind==='margin_level'?den:'',instant:tags.data?.find(t=>t.tag===metric)?.instant ?? reason?.instant ?? false,
      rule_definition:{version:1,preset,evaluation_period:period}}
    return reason ? (await apiClient.patch(`/reasons/${encodeURIComponent(reason.reason_key)}`,payload)).data
      : {...(await apiClient.post('/reasons',payload)).data,reason_key:payload.reason_key}
  },onSuccess:async(data)=>{
    await Promise.all(['reasons','screen','report','portfolio'].map(key=>q.invalidateQueries({queryKey:[key]})))
    onDone?.(data.reason_key ?? reason?.reason_key ?? '')
  }})
  function submit(e:FormEvent){e.preventDefault();if(confirmed)mutation.mutate()}
  const valid=preset!=='custom' || (!!metric && !!description.trim() && threshold.trim()!=='' && Number.isFinite(Number(threshold)) && (kind!=='margin_level'||!!den))
  return <form onSubmit={submit} onChange={()=>setConfirmed(false)} className="flex flex-col gap-4">
    <div><p className="section-eyebrow">Investment Reason Builder</p><h2 className="mt-1 text-xl font-semibold">{th?'เพิ่มเหตุผลการลงทุน':'Build your investment reason'}</h2><p className="mt-2 text-sm text-muted-foreground">{th?'เลือกสิ่งที่คุณคาดหวัง แล้วตรวจสอบกฎก่อนบันทึก':'Choose what matters to you, then review the exact rule.'}</p></div>
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]"><div className="space-y-5">
    <fieldset><legend className="mb-3 text-sm font-semibold">1. {th?'ต้องการติดตามเรื่องอะไร?':'What would you like to monitor?'}</legend>
    <div className="grid grid-cols-2 gap-2">{[
      {value:'Revenue',label:th?'การเติบโตของรายได้':'Revenue growth',icon:TrendingUp},
      {value:'Profitability',label:th?'ความสามารถในการทำกำไร':'Profitability',icon:ChartNoAxesCombined},
      {value:'Debt',label:th?'ภาระหนี้สิน':'Long-term debt',icon:Landmark},
      {value:'Custom',label:th?'กำหนดเอง':'Custom metric',icon:SlidersHorizontal},
    ].map(({value,label,icon:Icon})=><label key={value} className="reason-choice text-xs"><input className="sr-only" type="radio" name="topic" value={value} checked={topic===value} onChange={()=>{setTopic(value);setPreset(presets.find(p=>p[0]===value)?.[1]??'custom');setConfirmed(false)}}/><Icon className="h-5 w-5 shrink-0 text-primary"/><span>{label}<small className="mt-1 block text-muted-foreground">{value}</small></span></label>)}</div></fieldset>
    <fieldset><legend className="mb-3 text-sm font-semibold">2. {th?'ความคาดหวังของคุณคืออะไร?':'What is your expectation?'}</legend><div className="space-y-2">
    {[...presets.filter(p=>p[0]===topic).map(p=>({value:p[1],label:p[th?2:3]})),{value:'custom',label:th?'กำหนดเปอร์เซ็นต์ด้วยตัวเอง':'Set my own percentage'}].map(o=><label className="reason-choice text-sm" key={o.value}><input type="radio" name="expectation" checked={preset===o.value} onChange={()=>{setPreset(o.value);setConfirmed(false)}}/>{o.label}</label>)}
    {onNatural&&<button type="button" className="reason-choice w-full text-sm text-primary" onClick={onNatural}><Sparkles className="h-4 w-4"/>{th?'ให้ AI ช่วยตรวจเหตุผลเชิงคุณภาพ':'Investigate a qualitative thesis with AI'}</button>}
    </div></fieldset>
    <fieldset><legend className="mb-3 text-sm font-semibold">3. {th?'รอบการตรวจสอบ':'Evaluation period'}</legend><div className="space-y-2">{[{value:'quarterly',label:th?'รายไตรมาส เทียบงวดเดียวกันปีก่อน':'Quarterly — same quarter last year'},{value:'annual',label:th?'รายปีบัญชี':'Fiscal year'}].map(o=><label className="flex gap-3 text-sm" key={o.value}><input type="radio" name="period" checked={period===o.value} onChange={()=>{setPeriod(o.value as 'quarterly'|'annual');setConfirmed(false)}}/>{o.label}</label>)}</div></fieldset>
    {preset==='custom' && <>
      <FinancialDataOrigin/>
      <label className="text-sm">{th?'ชื่อเหตุผล':'Reason name'}<Input value={description} onChange={e=>setDescription(e.target.value)} required maxLength={1000}/></label>
      <label className="text-sm">{th?'รายการข้อมูลทางการเงิน':'Financial item'}</label>
      <Select searchable value={metric} onChange={v=>{setMetric(v);setConfirmed(false)}} options={options}/>
      <FinancialTagInfo tag={tags.data?.find(t=>t.tag===metric)}/>
      {tags.isError && <p role="alert">{th?'โหลดรายการข้อมูลไม่ได้ กรุณาลองอีกครั้ง':'Could not load financial items'}</p>}
      <Select value={kind} onChange={v=>{setKind(v as ReasonKind);setConfirmed(false)}} options={[{value:'yoy_growth',label:'YoY growth (%)'},{value:'margin_level',label:'Ratio (%)'}]}/>
      {kind==='margin_level' && <><label>{th?'ตัวหาร':'Denominator'}</label><Select searchable value={den} onChange={v=>{setDen(v);setConfirmed(false)}} options={options}/></>}
      <div className="flex gap-3"><Select value={op} onChange={v=>{setOp(v as ComparisonOp);setConfirmed(false)}} options={['>','>=','<','<='].map(value=>({value,label:value}))}/><Input aria-label="Threshold percent" type="number" step="any" value={threshold} onChange={e=>setThreshold(e.target.value)} required/><span>%</span></div>
    </>}
    <label className="block text-sm">{th?'เหตุผลเพิ่มเติม (ไม่บังคับ)':'Original rationale (optional)'}<textarea className="mt-2 min-h-24 w-full rounded-lg border bg-[var(--bg-input)] p-3" value={original} onChange={e=>setOriginal(e.target.value)} maxLength={5000} placeholder={th?'เช่น เชื่อว่าธุรกิจ Services จะช่วยรักษารายได้ในระยะยาว':'For example, Services could support recurring revenue.'}/></label>
    </div><aside className="space-y-4 rounded-xl border border-primary/15 bg-primary/5 p-5 lg:sticky lg:top-0 lg:self-start" aria-label="Rule preview"><div className="flex items-center gap-2 font-semibold"><ShieldCheck className="h-5 w-5 text-primary"/>{th?'ตัวอย่างเหตุผลที่จะบันทึก':'Your thesis preview'}</div>
      <p className="text-base font-semibold">{label|| (th?'กำหนดรายละเอียดของคุณ':'Define your rule')}</p>
      <p className="text-xs text-muted-foreground">{th?'รอบการประเมิน':'Evaluation period'}: {period==='annual'?(th?'รายปีบัญชี':'Fiscal year'):(th?'รายไตรมาส':'Standalone quarter')}</p>
      <div className="rounded-lg border bg-[var(--bg-card)] p-3"><p className="mb-2 text-xs font-semibold">{th?'กฎที่จะใช้ตรวจสอบ':'Exact verification rule'}</p><code className="break-words text-xs">{preview}</code></div>
      {original&&<p className="whitespace-pre-wrap break-words text-sm">{original}</p>}
      <p className="text-xs leading-relaxed text-muted-foreground">SEC EDGAR · 10-Q / 10-K · USD · consolidated</p>
      <p className="text-xs leading-relaxed text-muted-foreground">{th?'ข้อมูลไม่ครบ หน่วยหรืองวดไม่ตรง: ไม่ประเมิน ไม่ถือว่าผิดเกณฑ์':'Missing or mismatched data: NOT_EVALUATED, not a breach.'}</p>
      {topic==='Debt'&&<p className="text-xs text-muted-foreground">{th?'หนี้ระยะยาวส่วนไม่หมุนเวียน ไม่รวมส่วนครบกำหนดปีนี้และหนี้สัญญาเช่า':'Noncurrent debt only; excludes current portion and leases.'}</p>}
    </aside></div>
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={e=>{e.stopPropagation();setConfirmed(e.target.checked)}}/>{th?'ยืนยันว่ากฎนี้ตรงกับความคาดหวังของฉัน':'I confirm this rule matches my expectation'}</label>
    {reason && <p className="text-xs text-muted-foreground">{th?'การแก้ไขไม่เปลี่ยน snapshot ของรายการซื้อเดิม':'Existing purchase snapshots remain unchanged.'}</p>}
    {mutation.isError && <p role="alert" className="text-destructive text-sm">{getApiErrorMessage(mutation.error)}</p>}
    <Button type="submit" disabled={!confirmed||!valid||mutation.isPending}><CheckCircle2 className="h-4 w-4"/>{th?'บันทึกเหตุผล':'Save reason'}</Button>
  </form>
}

export function FlexibleReasonForm(props:{reason?:Reason;onDone?:(key:string)=>void;ticker?:string}){
 const {lang}=useTranslation()
 const [type,setType]=useState(props.reason?.rule_definition?.thesis_type==='NATURAL_LANGUAGE'?'natural':'structured')
 return <div className="space-y-4">
  {!props.reason && <div className="grid grid-cols-2 gap-2 border-b pb-4">{[{value:'structured',label:lang==='th'?'ตัวเลข / ทิศทาง':'Numeric / Directional',icon:SlidersHorizontal},{value:'natural',label:lang==='th'?'เขียนเหตุผลด้วยตัวเอง':'Natural-language thesis',icon:Sparkles}].map(({value,label,icon:Icon})=><button type="button" key={value} aria-pressed={type===value} className="reason-choice text-sm" onClick={()=>setType(value)}><Icon className="h-4 w-4 text-primary"/>{label}</button>)}</div>}
  {type==='natural'?<NaturalReasonForm {...props}/>:<StructuredReasonForm {...props} onNatural={!props.reason?()=>setType('natural'):undefined}/>}

 </div>
}
