import { useTranslation } from "@/i18n/context"
import type { ReportReason } from "@/types"

export type RiskLevel = "low" | "moderate" | "high" | "unknown"

// Derived from this project's own real Evidence Layer -- the same
// Supported/Weakened/Broken statuses the dashboard's reason cards show,
// not a separately-fabricated "risk score". Any Broken reason -> high;
// any Weakened/Not-enough-data -> moderate; everything Supported -> low.
export function riskLevelFor(reasons: ReportReason[]): RiskLevel {
  if (reasons.length === 0) return "unknown"
  if (reasons.some((r) => r.status === "Broken")) return "high"
  if (reasons.some((r) => r.status === "Weakened" || r.status === "Not enough data")) return "moderate"
  return "low"
}

const POSITION: Record<RiskLevel, number> = { low: 15, moderate: 50, high: 85, unknown: 50 }

export function RiskMeter({ level }: { level: RiskLevel }) {
  const { t } = useTranslation()
  if (level === "unknown") return null

  return (
    <div className="flex flex-col gap-2 rounded-lg bg-[var(--bg-sidebar)] p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-[var(--text-primary)]">{t("risk_meter_title")}</span>
        <span
          className={{
            low: "rounded-full bg-status-supported/15 px-2 py-0.5 text-[11px] font-semibold text-status-supported",
            moderate: "rounded-full bg-status-weakened/15 px-2 py-0.5 text-[11px] font-semibold text-status-weakened",
            high: "rounded-full bg-status-broken/15 px-2 py-0.5 text-[11px] font-semibold text-status-broken",
          }[level]}
        >
          {t(`risk_level_${level}`)}
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-gradient-to-r from-status-supported via-status-weakened to-status-broken">
        <div
          className="absolute top-1/2 h-3.5 w-3.5 -translate-y-1/2 rounded-full border-2 border-[var(--bg-card)] bg-white shadow"
          style={{ left: `${POSITION[level]}%`, transform: "translate(-50%, -50%)" }}
        />
      </div>
      <p className="text-[11px] text-[var(--text-muted)]">{t("risk_meter_caption")}</p>
    </div>
  )
}
