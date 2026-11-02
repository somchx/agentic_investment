import { CheckCircle2, HelpCircle, XCircle } from 'lucide-react'
import type { Reason, ScreenCompany, ScreenReasonResult } from '@/types'
import { useTranslation } from '@/i18n/context'
import { useCompanies } from '@/hooks/use-companies'

// Plain-language reading of one company's screen results, built only from
// the numbers the deterministic screen already returned -- no LLM, so the
// sentence can never say anything the rule check didn't compute.

type Outcome = 'pass' | 'fail' | 'unknown'

const BUILTIN_LABELS: Record<string, { en: string; th: string }> = {
  revenue_growth: { en: 'Revenue', th: 'รายได้' },
  operating_margin: { en: 'Operating margin', th: 'Operating Margin' },
  debt_growth: { en: 'Long-term debt (as tagged in the filing)', th: 'หนี้ระยะยาวตามรายการที่ระบบใช้' },
}

function outcomeOf(r: ScreenReasonResult | undefined): Outcome {
  if (!r?.status) return 'unknown'
  if (r.rule_status === 'SATISFIED') return 'pass'
  if (r.rule_status === 'BREACHED') return 'fail'
  if (r.rule_status === 'NOT_EVALUATED') return 'unknown'
  if (r.status === 'Supported') return 'pass'
  if (r.status === 'Weakened' || r.status === 'Broken') return 'fail'
  return 'unknown'
}

function fmt(value: number, unit: string | undefined, signed = false) {
  const v = signed ? Math.abs(value) : value
  return unit === 'USD'
    ? `${v.toLocaleString(undefined, { maximumFractionDigits: 2 })} USD`
    : `${(v * 100).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`
}

// Thai has no spaces between words, but an English term next to Thai text reads better with one.
const latinEnd = (text: string) => /[A-Za-z0-9)]$/.test(text)
const latinStart = (text: string) => /^[A-Za-z0-9(]/.test(text)
const thaiJoin = (a: string, b: string) => a + (latinEnd(a) || latinStart(b) ? ' ' : '') + b

export function CompanySummary({ company, reasonKeys, reasons }: { company: ScreenCompany; reasonKeys: string[]; reasons: Reason[] | undefined }) {
  const { lang, tReason, tXbrlTag } = useTranslation()
  const th = lang === 'th'
  const { data: companies } = useCompanies()
  // SEC reports some registrant names in capitals ("AMAZON COM INC"); prefer the app's display name.
  const name = companies?.find(c => c.ticker === company.ticker)?.name ?? company.company_name

  const items = reasonKeys.map(key => {
    const r = company.by_reason[key]
    const rule = reasons?.find(reason => reason.reason_key === key)
    const builtin = BUILTIN_LABELS[key]
    const label = builtin ? builtin[lang]
      : rule && !rule.rule_definition ? (rule.kind === 'margin_level' && rule.denominator_metric
        ? `${tXbrlTag(rule.metric, rule.metric)} / ${tXbrlTag(rule.denominator_metric, rule.denominator_metric)}`
        : tXbrlTag(rule.metric, rule.metric))
      : tReason(key, r?.description ?? rule?.description ?? key)
    return { key, r, rule, label, outcome: outcomeOf(r) }
  })

  const passed = items.filter(i => i.outcome === 'pass')
  const failed = items.filter(i => i.outcome === 'fail')
  const unknown = items.filter(i => i.outcome === 'unknown')

  function sentence({ r, rule, label, outcome }: (typeof items)[number]) {
    if (outcome === 'unknown' || r?.computed_value == null) {
      return th ? `${label}: ข้อมูลไม่พอสำหรับตรวจเกณฑ์นี้` : `${label}: not enough data to check this rule`
    }
    const value = r.computed_value
    const unit = r.value_unit
    const threshold = r.comparison_value ?? rule?.threshold ?? null
    const growth = rule?.kind === 'yoy_growth' && !rule.rule_definition
    const movement = growth
      ? (value >= 0 ? (th ? `เพิ่มขึ้น ${fmt(value, unit, true)}` : `grew ${fmt(value, unit, true)}`)
        : (th ? `ลดลง ${fmt(value, unit, true)}` : `fell ${fmt(value, unit, true)}`))
      : (th ? `อยู่ที่ ${fmt(value, unit)}` : `is ${fmt(value, unit)}`)
    if (threshold == null) return th ? thaiJoin(label, movement) : `${label} ${movement}`
    const relation = value > threshold ? (th ? 'สูงกว่า' : 'above') : value < threshold ? (th ? 'ต่ำกว่า' : 'below') : (th ? 'เท่ากับ' : 'equal to')
    const far = outcome === 'fail' && r.status === 'Broken' ? (th ? ' มาก' : ' by a wide margin') : ''
    const verdict = outcome === 'pass' ? (th ? 'ผ่านเกณฑ์' : 'passes') : (th ? 'ไม่ผ่านเกณฑ์' : 'fails')
    return th
      ? `${thaiJoin(label, movement)} ${relation}เกณฑ์ ${fmt(threshold, unit)}${far} — ${verdict}`
      : `${label} ${movement}, ${relation} the ${fmt(threshold, unit)} threshold${far} — ${verdict}`
  }

  const join = (list: typeof items) => {
    const labels = list.map(i => i.label)
    const last = labels.pop() as string
    if (!labels.length) return last
    return th ? thaiJoin(`${labels.join(', ')} และ`, last) : `${labels.join(', ')} and ${last}`
  }
  let meaning: string
  if (passed.length === items.length) {
    meaning = th ? 'ตัวเลขทุกด้านที่เลือกยังเป็นไปตามความคาดหวังที่กำหนดไว้' : 'Every selected rule still holds on the reported numbers.'
  } else if (failed.length === items.length) {
    meaning = th ? 'ตัวเลขไม่เป็นไปตามเกณฑ์ที่กำหนดไว้ในทุกด้านที่เลือก' : 'None of the selected rules hold on the reported numbers.'
  } else {
    const parts: string[] = []
    if (passed.length) parts.push(th ? thaiJoin('ยังผ่านเกณฑ์ด้าน', join(passed)) : `still meets the ${join(passed)} rule${passed.length > 1 ? 's' : ''}`)
    if (failed.length) parts.push(th ? thaiJoin('ไม่ผ่านเกณฑ์ด้าน', join(failed)) : `fails on ${join(failed)}`)
    if (unknown.length) parts.push(th ? thaiJoin(thaiJoin('ยังสรุปด้าน', join(unknown)), 'ไม่ได้เพราะข้อมูลไม่พอ') : `can't be judged on ${join(unknown)} (not enough data)`)
    meaning = th ? `${name} ${parts.join(' แต่')}` : `${name} ${parts.join(', but ')}.`
  }

  const tone = failed.length ? 'text-destructive' : unknown.length ? 'text-[var(--text-muted)]' : 'text-status-supported'

  return (
    <div className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-card)] p-4">
      <h3 className="text-sm font-semibold">
        {name} <span className="font-mono-num text-muted-foreground">({company.ticker})</span>
        <span className={`ml-2 ${tone}`}>— {th ? `ผ่าน ${passed.length}/${items.length} ข้อ` : `passes ${passed.length}/${items.length}`}</span>
      </h3>
      <ul className="mt-2 space-y-1 text-sm">
        {items.map(item => (
          <li key={item.key} className="flex items-start gap-2">
            {item.outcome === 'pass' ? <CheckCircle2 className="mt-0.5 h-4 w-4 flex-none text-status-supported" />
              : item.outcome === 'fail' ? <XCircle className="mt-0.5 h-4 w-4 flex-none text-destructive" />
              : <HelpCircle className="mt-0.5 h-4 w-4 flex-none text-muted-foreground" />}
            <span>{sentence(item)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-sm"><span className="font-semibold">{th ? 'ความหมาย' : 'What this means'}:</span> {meaning}</p>
    </div>
  )
}
