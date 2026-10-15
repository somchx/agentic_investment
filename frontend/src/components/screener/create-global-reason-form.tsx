import { FinancialDataOrigin, FinancialTagInfo, FinancialFormulaInfo } from "@/components/screener/financial-data-info"
import { useState, type FormEvent } from "react"
import { FlaskConical } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { useAllXbrlTags, useCreateReason } from "@/hooks/use-reasons"
import { getApiErrorMessage } from "@/api/client"
import type { ComparisonOp, ReasonKind } from "@/types"
import { useTranslation } from "@/i18n/context"

const selectTriggerClass =
  "flex w-full items-center justify-between gap-2 rounded border border-[var(--border-primary)] bg-[var(--bg-input)] px-3 py-1.5 text-sm text-[var(--text-primary)] disabled:opacity-60"

// A single global rule applies to every company; missing evidence is skipped.
export function CreateGlobalReasonForm({ onDone }: { onDone?: () => void }) {
  const { t, tXbrlTag } = useTranslation()
  const { data: tags, isLoading: tagsLoading } = useAllXbrlTags()
  const createReason = useCreateReason()

  const COMPARISON_OPTIONS: { value: ComparisonOp; label: string }[] = [
    { value: ">", label: t("create_reason_comparison_gt") },
    { value: ">=", label: t("create_reason_comparison_gte") },
    { value: "<", label: t("create_reason_comparison_lt") },
    { value: "<=", label: t("create_reason_comparison_lte") },
  ]

  const KIND_OPTIONS: { value: ReasonKind; label: string }[] = [
    { value: "yoy_growth", label: t("create_reason_kind_growth") },
    { value: "margin_level", label: t("create_reason_kind_ratio") },
  ]

  const [metric, setMetric] = useState("")
  const [denominatorMetric, setDenominatorMetric] = useState("")
  const [comparison, setComparison] = useState<ComparisonOp>(">")
  const [kind, setKind] = useState<ReasonKind>("yoy_growth")
  const [threshold, setThreshold] = useState("")
  const [description, setDescription] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const metricOptions = (tags ?? []).map((tag) => ({
    value: tag.tag,
    label: tXbrlTag(tag.tag, tag.label, tag.label_th),
  }))
  const selectedTag = tags?.find((tag) => tag.tag === metric)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    if (!metric || !selectedTag) {
      setError(t("create_reason_err_pick_metric"))
      return
    }
    if (!description.trim()) {
      setError(t("create_reason_err_description"))
      return
    }
    const parsedThreshold = Number(threshold)
    if (!threshold.trim() || !Number.isFinite(parsedThreshold)) {
      setError(t("create_reason_err_threshold"))
      return
    }
    if (kind === "margin_level" && !denominatorMetric) {
      setError(t("create_reason_err_denominator"))
      return
    }
    const slug = metric.toLowerCase().replace(/[^a-z0-9]+/g, "_")
    try {
      await createReason.mutateAsync({
        reason_key: `custom_global_${slug}_${crypto.randomUUID()}`,
        ticker: null,
        preview_ticker: selectedTag.tickers?.[0],
        metric,
        comparison,
        threshold: parsedThreshold / 100,
        kind,
        denominator_metric: kind === "margin_level" ? denominatorMetric : "",
        description: description.trim(),
        instant: selectedTag.instant,
      })
    } catch (error) {
      setError(getApiErrorMessage(error, t("create_reason_err_default")))
      return
    }
    setMetric("")
    setDenominatorMetric("")
    setThreshold("")
    setDescription("")
    setKind("yoy_growth")
    setComparison(">")
    setSuccess(t("create_global_reason_success"))
    onDone?.()
  }

  return (
    <Panel
      title={t("create_global_reason_title")}
      description={t("create_global_reason_description")}
      color="var(--brand-secondary)"
    >
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        {/* Custom reasons work everywhere in the app, but the research only evaluates the three core ones. */}
        <p className="flex items-start gap-2 rounded-md border border-primary/30 bg-primary/5 p-3 text-xs text-[var(--text-secondary)]">
          <FlaskConical className="mt-0.5 h-3.5 w-3.5 flex-none text-primary" aria-hidden="true" />
          {t("custom_reason_research_scope")}
        </p>
          <FinancialDataOrigin />
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="global-reason-description">{t("create_reason_field_description")}</Label>
          <Input
            id="global-reason-description"
            placeholder={t("create_reason_description_placeholder")}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="global-reason-metric">{t("create_reason_field_metric")}</Label>
          <Select
            id="global-reason-metric"
            value={metric}
            onChange={setMetric}
            disabled={tagsLoading}
            placeholder={tagsLoading ? t("create_reason_metric_loading") : t("create_reason_metric_placeholder")}
            className={selectTriggerClass}
            options={metricOptions}
            searchable
            searchPlaceholder={t("create_reason_search_placeholder")}
            noMatchesLabel={t("create_reason_no_matches")}
          />
        </div>

          <FinancialTagInfo tag={selectedTag} />

        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="global-reason-kind">{t("create_reason_field_kind")}</Label>
            <Select
              id="global-reason-kind"
              value={kind}
              onChange={(v) => setKind(v as ReasonKind)}
              className={selectTriggerClass}
              options={KIND_OPTIONS}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="global-reason-comparison">{t("create_reason_field_comparison")}</Label>
            <Select
              id="global-reason-comparison"
              value={comparison}
              onChange={(v) => setComparison(v as ComparisonOp)}
              className={selectTriggerClass}
              options={COMPARISON_OPTIONS}
            />
          </div>
        </div>

        {kind === "margin_level" && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="global-reason-denominator">{t("create_reason_field_denominator")}</Label>
            <Select
              id="global-reason-denominator"
              value={denominatorMetric}
              onChange={setDenominatorMetric}
              placeholder={t("create_reason_denominator_placeholder")}
              className={selectTriggerClass}
              options={metricOptions}
              searchable
              searchPlaceholder={t("create_reason_search_placeholder")}
              noMatchesLabel={t("create_reason_no_matches")}
            />
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="global-reason-threshold">{t("create_reason_field_threshold")}</Label>
          <div className="relative">
<Input className="pr-9"
            id="global-reason-threshold"
            type="number"
            step="any"
            placeholder={t("create_reason_threshold_placeholder")}
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
          />
<span aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-muted-foreground">%</span>
</div>
        </div>

        <FinancialFormulaInfo kind={kind} metric={metric} denominator={denominatorMetric} comparison={comparison} threshold={threshold} />
          {kind === "margin_level" && <FinancialTagInfo tag={tags?.find(tag => tag.tag === denominatorMetric)} />}

          {error && <p className="text-sm text-destructive">{error}</p>}
        {success && <p className="text-sm text-status-supported">{success}</p>}

        <Button type="submit" disabled={createReason.isPending}>
          {createReason.isPending ? t("create_reason_submit_pending") : t("create_reason_submit")}
        </Button>
      </form>
    </Panel>
  )
}
