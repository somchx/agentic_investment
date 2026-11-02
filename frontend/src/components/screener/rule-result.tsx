import type { RuleEvaluationFields } from '@/types'
import { useTranslation } from '@/i18n/context'
export function formatThesisValue(value:number|null|undefined,unit?:string){
  if(value==null)return '—'
  return unit==='USD'?`${value.toLocaleString(undefined,{maximumFractionDigits:2})} USD`:`${(value*100).toLocaleString(undefined,{maximumFractionDigits:2})}%`
}
export function RuleResult({result}:{result:RuleEvaluationFields & {computed_value?:number|null;explanation?:string}}){
 const {lang}=useTranslation();const th=lang==='th'
 return <div className="space-y-1 text-xs">
  <p>{th?'ผลคำนวณ':'Rule'}: <strong>{result.rule_status ?? 'NOT_EVALUATED'}</strong></p>
  <p>{th?'หลักฐานตัวเลข':'Numeric evidence'}: {result.evidence_status ?? 'INSUFFICIENT'}</p>
  {result.rule_definition && <><p className="break-words">{result.rule_definition.preview}</p><p>{result.rule_definition.evaluation_period}</p>
   <p className="font-mono-num">{formatThesisValue(result.computed_value,result.value_unit)} {result.comparison_value!=null && ` / ${th?'ค่าเปรียบเทียบ':'comparison'} ${formatThesisValue(result.comparison_value,result.value_unit)}`}</p></>}
  {result.explanation && <p className="text-muted-foreground">{result.explanation}</p>}
 </div>
}
