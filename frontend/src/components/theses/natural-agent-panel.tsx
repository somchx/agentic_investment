import {useState} from 'react'
import {useReasons} from '@/hooks/use-reasons'
import {Select} from '@/components/ui/select'
import {NaturalInvestigationPanel} from './natural-investigation-panel'
export function NaturalAgentPanel(){
 const {data}=useReasons();const rows=(data||[]).filter(r=>r.rule_definition?.thesis_type==='NATURAL_LANGUAGE')
 const [key,setKey]=useState('');const current=rows.find(r=>r.reason_key===key)
 if(!rows.length)return null
 return <details className="mb-3 rounded-lg border p-3 max-h-[65vh] overflow-y-auto">
  <summary className="cursor-pointer text-sm font-medium">Natural-language Thesis · ตรวจหลักฐานเหตุผลเชิงธุรกิจ</summary>
  <div className="space-y-3 pt-3"><Select value={key} onChange={setKey} options={[{value:'',label:'เลือกเหตุผล / Select thesis'},...rows.map(r=>({value:r.reason_key,label:`${r.ticker} · ${r.description}`}))]}/>
   {current?.rule_definition&&<NaturalInvestigationPanel key={key} reasonKey={key} definition={current.rule_definition}/>}</div>
 </details>
}
