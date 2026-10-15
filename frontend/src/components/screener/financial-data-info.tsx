import { useTranslation } from "@/i18n/context"
import { xbrlTagLabelsTh } from "@/i18n/translations"
import type { XbrlTag, ReasonKind } from "@/types"

export function FinancialDataOrigin() {
  const { t } = useTranslation()
  return <div className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-hover)] p-3 text-xs leading-relaxed text-[var(--text-muted)]">
    <p className="font-semibold text-[var(--text-primary)]">{t("financial_origin_title")}</p>
    <p className="mt-1">{t("financial_origin_body")}</p>
    <a className="mt-1 inline-block text-primary underline" href="https://www.sec.gov/search-filings/edgar-application-programming-interfaces" target="_blank" rel="noreferrer">{t("financial_sec_docs")}</a>
  </div>
}

export function FinancialTagInfo({ tag }: { tag?: XbrlTag }) {
  const { t } = useTranslation()
  if (!tag) return null
  return <div className="min-w-0 rounded-lg border border-[var(--border-primary)] p-3 text-xs leading-relaxed text-[var(--text-muted)]">
    <div className="mb-3 border-b border-[var(--border-primary)] pb-3">
      <p lang="th" className="break-words font-semibold text-[var(--text-primary)]">{xbrlTagLabelsTh[tag.tag] ?? tag.label_th ?? t("financial_thai_name_unavailable")}</p>
      <p lang="en" className="mt-1 break-words">{tag.label}</p>
      <p className="mt-1 break-all font-mono-num">XBRL: {tag.tag}</p>
    </div>
    <p className="font-semibold text-[var(--text-primary)]">{t("financial_definition")}</p>
    <p className="mt-1 break-words" lang="en">{tag.description || t("financial_no_definition")}</p>
    <p className="mt-2">{t(tag.instant ? "financial_instant" : "financial_duration")}</p>
    {tag.source ? <div className="mt-2">
      <p className="font-semibold">{t("financial_filing_example")}</p>
      <a href={tag.source.url} target="_blank" rel="noreferrer" className="break-words text-primary underline">{tag.source.company} · {tag.source.form} · {tag.source.filed}</a>
      <p>{t("financial_period_end")}: {tag.source.period_end ?? "—"}</p>
    </div> : <p className="mt-2">{t("financial_no_source")}</p>}
  </div>
}

export function FinancialFormulaInfo({ kind, metric, denominator, comparison, threshold }: {
  kind: ReasonKind; metric: string; denominator: string; comparison: string; threshold: string
}) {
  const { t } = useTranslation()
  const valid = threshold.trim() !== "" && Number.isFinite(Number(threshold))
  return <div className="rounded-lg bg-[var(--bg-hover)] p-3 text-xs leading-relaxed text-[var(--text-muted)]">
    <p className="font-semibold text-[var(--text-primary)]">{t("financial_formula_title")}</p>
    <p className="mt-1">{t(kind === "yoy_growth" ? "financial_formula_yoy" : "financial_formula_ratio")}</p>
    <p className="mt-1 break-all font-mono-num">{metric || "A"}{kind === "margin_level" ? ` / ${denominator || "B"}` : " (YoY)"} {comparison} {valid ? `${threshold}%` : "…"}</p>
    <p className="mt-2">{t("financial_threshold_hint")}</p>
    <p className="mt-1">{t("financial_missing_hint")}</p>
  </div>
}
