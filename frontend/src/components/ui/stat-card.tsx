import type { ReactNode } from "react"

export function StatCard({
  label,
  value,
  accent = "#58a6ff",
  suffix,
}: {
  label: ReactNode
  value: ReactNode
  accent?: string
  suffix?: ReactNode
}) {
  return (
    <div
      className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-card)] p-3"
      style={{ borderTop: `3px solid ${accent}` }}
    >
      <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">{label}</div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-xl font-bold text-[var(--text-primary)]">{value}</span>
        {suffix && <span className="text-xs text-[var(--text-muted)]">{suffix}</span>}
      </div>
    </div>
  )
}
