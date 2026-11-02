import { useState } from 'react'
import { FileText, Printer, Download, ShieldCheck } from 'lucide-react'
import { useTranslation } from '@/i18n/context'
import { useCompanies } from '@/hooks/use-companies'
import { useReport } from '@/hooks/use-report'
import { useLatestInvestigation } from '@/hooks/use-report'
import { PageHeader } from '@/components/ui/page-header'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
import { RuleResult } from '@/components/screener/rule-result'

export function ReportsPage(){
 const {lang}=useTranslation();const th=lang==='th'
 const {data:companies}=useCompanies();const [ticker,setTicker]=useState('AAPL')
 const {data:report,isLoading,isError}=useReport(ticker)
 const {data:investigation}=useLatestInvestigation(ticker)
 function download(){const blob=new Blob([JSON.stringify({exported_at:new Date().toISOString(),company_report:report,stored_investigation:investigation??null},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`ReasonCheck-${ticker}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
 return <div className="space-y-6">
  <PageHeader icon={FileText} title={th?'รายงานและส่งออก':'Reports & Export'} subtitle={th?'รวบรวมผลที่มีอยู่เพื่อทบทวนและนำไปปรึกษาผู้เชี่ยวชาญ':'Review existing results and prepare for a discussion with your adviser.'}/>
  <div className="finance-card no-print flex flex-wrap items-end gap-4"><div className="min-w-48 flex-1"><label className="mb-2 block text-sm">{th?'บริษัท':'Company'}</label><Select value={ticker} onChange={setTicker} options={(companies??[]).map(c=>({value:c.ticker,label:`${c.ticker} — ${c.name}`}))}/></div><Button variant="outline" disabled={!report||isLoading||isError} onClick={download}><Download/>{th?'ดาวน์โหลด JSON':'Download JSON'}</Button><Button disabled={!report||isLoading||isError} onClick={()=>window.print()}><Printer/>{th?'พิมพ์ / บันทึก PDF':'Print / Save PDF'}</Button></div>
  {isLoading&&<p role="status">{th?'กำลังจัดเตรียมรายงาน…':'Preparing report…'}</p>}
  {isError&&<p role="alert" className="text-destructive">{th?'โหลดรายงานไม่ได้ กรุณาลองใหม่':'Unable to load report. Please retry.'}</p>}
  {report&&!isError&&<article className="finance-card space-y-6">
    <div className="flex items-start justify-between gap-3 border-b pb-5"><div><p className="section-eyebrow">ReasonCheck / Thesis Review</p><h2 className="mt-2 text-2xl">{ticker} — {report.company_name}</h2></div><ShieldCheck className="h-8 w-8 text-primary"/></div>
    <p className="text-xs text-muted-foreground">{th?'ส่งออก ณ':'Exported at'} {new Date().toLocaleDateString(lang==='th'?'th-TH':'en-US')} · {th?'วันที่ประเมินของแต่ละเหตุผลแสดงด้านล่าง':'Each reason retains its own evaluation date below.'}</p>
    {report.reasons.map(r=><section key={r.reason_key} className="rounded-xl border p-4"><h3 className="mb-3 text-base">{r.description}</h3><RuleResult result={r}/><p className="mt-3 text-xs text-muted-foreground">As of: {r.as_of??'—'}</p></section>)}
    {!report.reasons.length&&<p>{th?'ยังไม่มีผลการตรวจ':'No evaluation results available.'}</p>}
    <p className="rounded-xl bg-muted p-4 text-sm text-muted-foreground">{th?'รายงานนี้แสดงผลจากระบบต้นแบบ ต้องตรวจตัวเลข งวด และแหล่งอ้างอิงก่อนใช้งาน ไม่ใช่คำแนะนำซื้อขาย ดาวน์โหลด JSON เพื่อเก็บรายละเอียดรายงานและผลสืบค้นล่าสุดที่มีอยู่':'Prototype results require verification of values, periods and source evidence. This is not a trading recommendation. Download JSON for the report and the latest stored investigation.'}</p>
  </article>}
 </div>
}
