import { useTranslation } from "@/i18n/context"
import { cn } from "@/lib/utils"
import { formatRatio, formatRule } from "@/components/dashboard/reason-trend-chart"
import type { ComparisonOp, ReasonStatus } from "@/types"

const STATUS_FILL: Record<ReasonStatus, string> = {
  Supported: "bg-status-supported",
  Weakened: "bg-status-weakened",
  Broken: "bg-status-broken",
  "Not enough data": "bg-status-unknown",
}

export interface GaugeRow {
  label?: string
  value: number
  status: ReasonStatus
  title?: string
}

/** One or more values drawn as bars from zero on a shared scale, with the
 * rule's threshold as a dashed marker -- reads as "how far past / short of
 * the line", which a bare ratio never did. Rows share the scale so a
 * before/after pair compares directly. */
export function ThresholdGauge({
  rows,
  threshold,
  comparison,
  showRule = true,
}: {
  rows: GaugeRow[]
  threshold: number
  comparison: ComparisonOp
  showRule?: boolean
}) {
  const { t } = useTranslation()
  const values = rows.map((r) => r.value).concat(threshold, 0)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const lo = min - span * 0.05
  const hi = max + span * 0.05
  const pos = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`
  const zero = (0 - lo) / (hi - lo)

  return (
    <div className="flex w-full min-w-[160px] flex-col gap-1">
      {rows.map((r, i) => {
        const at = (r.value - lo) / (hi - lo)
        return (
          <div key={i} className="flex items-center gap-2" title={r.title}>
            {r.label && <span className="w-[4.25rem] flex-none text-[10px] text-[var(--text-muted)]">{r.label}</span>}
            <div className="relative h-2 flex-1 rounded-full bg-[var(--bg-hover)]">
              <div
                className={cn("absolute top-0 h-2 rounded-full", STATUS_FILL[r.status])}
                style={{ left: `${Math.min(zero, at) * 100}%`, width: `${Math.max(Math.abs(at - zero) * 100, 1)}%` }}
              />
              {/* Zero baseline, so a negative value visibly grows leftwards. */}
              {lo < 0 && <div className="absolute -top-0.5 h-3 w-px bg-[var(--text-muted)]" style={{ left: pos(0) }} aria-hidden="true" />}
              <div className="absolute -top-1 h-4 border-l border-dashed border-[var(--text-primary)]" style={{ left: pos(threshold) }} aria-hidden="true" />
            </div>
            <span className="w-14 flex-none text-right font-mono-num text-xs font-semibold text-[var(--text-primary)]">{formatRatio(r.value)}</span>
          </div>
        )
      })}
      {showRule && (
        <span className="flex items-center gap-1 text-[10px] text-[var(--text-muted)]">
          <span className="inline-block h-2.5 border-l border-dashed border-[var(--text-primary)]" aria-hidden="true" />
          {t("reason_chart_threshold", { rule: formatRule(comparison, threshold) })}
        </span>
      )}
    </div>
  )
}
