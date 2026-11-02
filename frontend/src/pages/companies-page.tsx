import { useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { ArrowLeft, Building2, Star, Plus } from 'lucide-react'
import { useTranslation } from '@/i18n/context'
import { useCompanies } from '@/hooks/use-companies'
import { useReport } from '@/hooks/use-report'
import { useReasons, useDeleteReason } from '@/hooks/use-reasons'
import { WatchlistTable } from '@/components/dashboard/watchlist-table'
import { CompanyDetailHeader } from '@/components/dashboard/company-detail-header'
import { InvestigationPanel } from '@/components/dashboard/investigation-panel'
import { NaturalInvestigationPanel } from '@/components/theses/natural-investigation-panel'
import { TickerAvatar } from '@/components/market/ticker-avatar'
import { PageHeader } from '@/components/ui/page-header'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'

function CompanyWorkspace({ticker}:{ticker:string}) {
 const {lang}=useTranslation(); const th=lang==='th'
 const {data:report,isLoading,isError}=useReport(ticker)
 const {data:reasons}=useReasons(ticker)
 const remove=useDeleteReason()
 const [tab,setTab]=useState('overview')
 return <Tabs value={tab} onValueChange={setTab} className="space-y-5">
  <TabsList className="h-auto max-w-full flex-wrap justify-start gap-2 bg-transparent p-0">
   <TabsTrigger value="overview">{th?'ภาพรวม':'Overview'}</TabsTrigger>
   <TabsTrigger value="theses">Investment Thesis</TabsTrigger>
   <TabsTrigger value="evidence">{th?'หลักฐานและการสืบค้น':'Evidence & Investigation'}</TabsTrigger>
  </TabsList>
  {isLoading&&<p role="status">{th?'กำลังโหลดข้อมูล…':'Loading company data…'}</p>}
  {isError&&<p role="alert" className="text-destructive">{th?'โหลดรายงานไม่ได้ กรุณาลองใหม่':'Could not load the company report. Please retry.'}</p>}
  <TabsContent value="overview"><CompanyDetailHeader ticker={ticker} onReview={()=>setTab('evidence')}/></TabsContent>
  <TabsContent value="theses" className="space-y-4">
   <div className="finance-card"><h2 className="text-lg">{ticker} — Investment Thesis</h2><p className="mt-1 text-sm text-muted-foreground">{th?'เหตุผลที่บันทึกไว้ พร้อมกฎและเวอร์ชันที่ยืนยัน':'Saved reasons, confirmed rules and thesis versions.'}</p>
    <div className="mt-5 divide-y">{reasons?.map((r,i)=><div key={r.reason_key} className="flex gap-4 py-4"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border text-primary">{i+1}</span><div><h3 className="text-sm">{r.description}</h3><p className="mt-1 text-xs text-muted-foreground">{r.rule_definition?.preview || r.original_text || r.metric}</p><span className="mt-2 inline-block rounded bg-primary/10 px-2 py-1 text-[10px] text-primary">{r.rule_definition?.thesis_type==='NATURAL_LANGUAGE'?'Natural-language':r.rule_definition?.preset==='custom'?'Numeric':'Structured'}{r.rule_definition?.version_no?` · v${r.rule_definition.version_no}`:''}</span></div></div>)}</div>
    {!reasons?.length&&!isLoading&&<p className="py-4 text-sm text-muted-foreground">{th?'ยังไม่มีเหตุผลที่สร้างไว้สำหรับบริษัทนี้':'No custom reasons saved for this company.'}</p>}
    <Button asChild variant="outline"><Link to="/screener"><Plus/>{th?'ดูเหตุผลพื้นฐาน':'View default reasons'}</Link></Button>
   </div>
   {reasons?.filter(r=>r.rule_definition?.thesis_type==='NATURAL_LANGUAGE').map(r=><div className="finance-card" key={r.reason_key}><NaturalInvestigationPanel reasonKey={r.reason_key} definition={r.rule_definition!}/></div>)}
  </TabsContent>
  <TabsContent value="evidence"><InvestigationPanel ticker={ticker} reasons={report?.reasons??[]} dataFreshness={report?.data_freshness} reasonsMeta={reasons} onDeleteReason={key=>remove.mutate(key)}/></TabsContent>
 </Tabs>
}
export function CompaniesPage({favoritesOnly=false}:{favoritesOnly?:boolean}) {
 const {lang}=useTranslation(); const th=lang==='th'
 const [params,setParams]=useSearchParams(); const {data:companies,isLoading}=useCompanies()
 const ticker=params.get('ticker')?.toUpperCase()
 const company=companies?.find(c=>c.ticker===ticker)
 return <div className="space-y-6">
  {ticker?<><button className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary" onClick={()=>setParams({})}><ArrowLeft size={16}/>{th?'กลับไปรายชื่อบริษัท':'Back to companies'}</button>
    <div className="flex items-center gap-4"><TickerAvatar ticker={ticker}/><div><h1 className="text-2xl">{ticker}</h1><p className="text-sm text-muted-foreground">{company?.name}</p></div></div>
    {company?<CompanyWorkspace key={ticker} ticker={ticker}/>:<p>{isLoading?(th?'กำลังโหลด…':'Loading…'):(th?'ไม่พบบริษัทในรายการที่รองรับ':'Company is not in the supported list.')}</p>}
   </>:<><PageHeader icon={favoritesOnly?Star:Building2} title={favoritesOnly?(th?'รายการติดตาม':'Watchlist'):(th?'บริษัท':'Companies')} subtitle={favoritesOnly?(th?'บริษัทที่คุณติดดาวไว้ในอุปกรณ์นี้':'Your starred companies, saved on this device.'):(th?'สำรวจบริษัท ทบทวนเหตุผล และตรวจหลักฐานต้นฉบับ':'Explore companies, revisit your thesis and inspect the evidence.')}/>
   <WatchlistTable favoritesOnly={favoritesOnly} onSelect={ticker=>setParams({ticker})}/></>}
 </div>
}
