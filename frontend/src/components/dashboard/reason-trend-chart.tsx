import { useState } from "react"
import { useTranslation } from "@/i18n/context"
import { cn } from "@/lib/utils"
import type { ComparisonOp, ReasonStatus } from "@/types"

const OP_SYMBOL: Record<ComparisonOp, string> = { ">": ">", ">=": "≥", "<": "<", "<=": "≤" }
const STATUS_DOT: Record<ReasonStatus, string> = {
  Supported: "bg-status-supported",
  Weakened: "bg-status-weakened",
  Broken: "bg-status-broken",
  "Not enough data": "bg-status-unknown",
}

// Both reason kinds (yoy_growth, margin_level) are ratios.
export function formatRatio(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

export function formatRule(comparison: ComparisonOp, threshold: number) {
  return `${OP_SYMBOL[comparison]} ${formatRatio(threshold)}`
}

const W = 300
const H = 56
const PAD_Y = 6

/** Single-series sparkline of a reason's value over recent filings, with the
 * rule's threshold as a dashed reference line (labelled beside the chart, not
 * on it, so it never collides with the line). Hover a point for its value. */
export function ReasonTrendChart({
  points,
  threshold,
}: {
  points: { as_of: string; value: number; status: ReasonStatus }[]
  threshold: number
}) {
  const { t } = useTranslation()
  const [hover, setHover] = useState<number | null>(null)

  const values = points.map((p) => p.value).concat(threshold)
  let min = Math.min(...values)
  let max = Math.max(...values)
  if (max - min < 1e-9) { min -= 0.05; max += 0.05 }
  const span = max - min
  min -= span * 0.1
  max += span * 0.1

  const x = (i: number) => (points.length === 1 ? W / 2 : (i / (points.length - 1)) * W)
  const y = (v: number) => PAD_Y + (1 - (v - min) / (max - min)) * (H - PAD_Y * 2)
  const pct = (px: number, total: number) => `${(px / total) * 100}%`
  const thresholdY = y(threshold)
  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ")
  const last = points.length - 1
  const active = hover ?? last

  return (
    <div className="relative h-14 w-full" role="img" aria-label={t("reason_chart_aria", { count: points.length })} onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible">
        <line x1={0} x2={W} y1={thresholdY} y2={thresholdY} stroke="var(--text-muted)" strokeWidth={1} strokeDasharray="4 3" vectorEffect="non-scaling-stroke" opacity={0.7} />
        <path d={line} fill="none" stroke="var(--chart-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      </svg>

      {/* Markers are HTML so they stay round while the SVG stretches to the row width. */}
      {points.map((p, i) => (
        <span
          key={p.as_of}
          className={cn(
            "pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-[var(--bg-card)] transition-opacity",
            STATUS_DOT[p.status],
            i === active ? "h-2.5 w-2.5 opacity-100" : "h-1.5 w-1.5 opacity-0",
          )}
          style={{ left: pct(x(i), W), top: pct(y(p.value), H) }}
        />
      ))}

      {/* Hit columns wider than the marks. */}
      <div className="absolute inset-0 flex">
        {points.map((p, i) => (
          <div key={p.as_of} className="h-full flex-1" onMouseEnter={() => setHover(i)} />
        ))}
      </div>

      {hover !== null && (
        <div
          className="pointer-events-none absolute bottom-full z-10 mb-1 -translate-x-1/2 whitespace-nowrap rounded-md border border-[var(--border-primary)] bg-[var(--bg-card)] px-2 py-1 text-[11px] shadow-md"
          style={{ left: `clamp(48px, ${pct(x(hover), W)}, calc(100% - 48px))` }}
        >
          <div className="font-mono-num font-semibold text-[var(--text-primary)]">{formatRatio(points[hover].value)}</div>
          <div className="text-[var(--text-muted)]">{points[hover].as_of}</div>
        </div>
      )}

    </div>
  )
}
