import { useState, type FormEvent } from "react"
import { Panel } from "@/components/ui/panel"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { useXbrlTags } from "@/hooks/use-reasons"
import { useCreateReason } from "@/hooks/use-reasons"
import { getApiErrorMessage } from "@/api/client"
import type { ComparisonOp, ReasonKind } from "@/types"
import { useTranslation } from "@/i18n/context"

const selectTriggerClass =
  "flex w-full items-center justify-between gap-2 rounded border border-[var(--border-primary)] bg-[var(--bg-input)] px-3 py-1.5 text-sm text-[var(--text-primary)] disabled:opacity-60"

export function CreateReasonForm({ ticker }: { ticker: string }) {
  const { t } = useTranslation()
  const { data: tags, isLoading: tagsLoading } = useXbrlTags(ticker)
  const createReason = useCreateReason()

  const COMPARISON_OPTIONS: { value: ComparisonOp; label: string }[] = [
    { value: ">", label: t("create_reason_comparison_gt") },
    { value: ">=", label: t("create_reason_comparison_gte") },
    { value: "<", label: t("create_reason_comparison_lt") },
    { value: "<=", label: t("create_reason_comparison_lte") },
  ]

  // Only two kinds actually exist server-side (reason_engine.py evaluates
  // just these two) -- "margin_level" needs a denominator metric, "yoy_growth" doesn't.
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
  const [success, setSuccess] = useState(false)

  const selectedTag = tags?.find((tag) => tag.tag === metric)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(false)
    if (!metric) {
      setError(t("create_reason_err_pick_metric"))
      return
    }
    if (!description.trim()) {
      setError(t("create_reason_err_description"))
      return
    }
    const parsedThreshold = Number(threshold)
    if (Number.isNaN(parsedThreshold)) {
      setError(t("create_reason_err_threshold"))
      return
    }
    if (kind === "margin_level" && !denominatorMetric) {
      setError(t("create_reason_err_denominator"))
      return
    }
    // reason_key is the DB primary key -- must be globally unique and can
    // never collide with the 3 built-ins (revenue_growth/operating_margin/
    // debt_growth), which a random per-ticker/timestamp slug guarantees.
    const reasonKey = `custom_${ticker.toLowerCase()}_${metric.toLowerCase().replace(/[^a-z0-9]+/g, "_")}_${Date.now().toString(36)}`
    try {
      await createReason.mutateAsync({
        reason_key: reasonKey,
        ticker,
        metric,
        comparison,
        threshold: parsedThreshold,
        kind,
        // Backend's denominator_metric is a plain `str = ""` field, not
        // Optional[str] -- it must always be a string, never null.
        denominator_metric: kind === "margin_level" ? denominatorMetric : "",
        description: description.trim(),
        instant: selectedTag?.instant ?? false,
      })
      setMetric("")
      setDenominatorMetric("")
      setThreshold("")
      setDescription("")
      setKind("yoy_growth")
      setComparison(">")
      setSuccess(true)
    } catch (err) {
      setError(getApiErrorMessage(err, t("create_reason_err_default")))
    }
  }

  return (
    <Panel title={t("create_reason_title")} description={t("create_reason_description", { ticker })} color="var(--accent-blue)">
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reason-description">{t("create_reason_field_description")}</Label>
            <Input
              id="reason-description"
              placeholder={t("create_reason_description_placeholder")}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reason-metric">{t("create_reason_field_metric")}</Label>
            <Select
              id="reason-metric"
              value={metric}
              onChange={setMetric}
              disabled={tagsLoading}
              placeholder={tagsLoading ? t("create_reason_metric_loading") : t("create_reason_metric_placeholder")}
              className={selectTriggerClass}
              options={(tags ?? []).map((tag) => ({ value: tag.tag, label: `${tag.label} (${tag.tag})` }))}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="reason-kind">{t("create_reason_field_kind")}</Label>
              <Select
                id="reason-kind"
                value={kind}
                onChange={(v) => setKind(v as ReasonKind)}
                className={selectTriggerClass}
                options={KIND_OPTIONS}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="reason-comparison">{t("create_reason_field_comparison")}</Label>
              <Select
                id="reason-comparison"
                value={comparison}
                onChange={(v) => setComparison(v as ComparisonOp)}
                className={selectTriggerClass}
                options={COMPARISON_OPTIONS}
              />
            </div>
          </div>

          {kind === "margin_level" && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="reason-denominator">{t("create_reason_field_denominator")}</Label>
              <Select
                id="reason-denominator"
                value={denominatorMetric}
                onChange={setDenominatorMetric}
                placeholder={t("create_reason_denominator_placeholder")}
                className={selectTriggerClass}
                options={(tags ?? []).map((tag) => ({ value: tag.tag, label: `${tag.label} (${tag.tag})` }))}
              />
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reason-threshold">{t("create_reason_field_threshold")}</Label>
            <Input
              id="reason-threshold"
              type="number"
              step="any"
              placeholder={t("create_reason_threshold_placeholder")}
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
          {success && <p className="text-sm text-status-supported">{t("create_reason_success")}</p>}

          <Button type="submit" disabled={createReason.isPending}>
            {createReason.isPending ? t("create_reason_submit_pending") : t("create_reason_submit")}
          </Button>
        </form>
    </Panel>
  )
}
