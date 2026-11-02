import { useMemo } from "react"
import { DonutChart, type DonutSegment } from "@/components/market/donut-chart"
import { usePortfolioSummary } from "@/hooks/use-positions"
import { useQuotes } from "@/hooks/use-market"
import { sectorFor } from "@/lib/sectors"
import { useTranslation } from "@/i18n/context"

// Allocation by sector (a true, static fact about each of this project's
// 15 known tickers -- see lib/sectors.ts), weighted by each holding's
// CURRENT market value (quantity x live price), not cost basis -- so this
// reflects today's actual exposure, not what was originally paid in.
const SECTOR_COLORS = [
  "text-[var(--chart-1)]",
  "text-[var(--chart-2)]",
  "text-[var(--chart-3)]",
  "text-[var(--chart-4)]",
  "text-[var(--chart-5)]",
  "text-[var(--chart-6)]",
]

export function PortfolioAllocationCard() {
  const { t } = useTranslation()
  const { data: summary } = usePortfolioSummary()

  const quantityByTicker = useMemo(() => {
    const map: Record<string, number> = {}
    for (const company of summary ?? []) {
      if (company.error != null) continue
      for (const p of company.positions) {
        map[company.ticker] = (map[company.ticker] ?? 0) + p.quantity
      }
    }
    return map
  }, [summary])

  const tickers = Object.keys(quantityByTicker)
  const { data: quotes } = useQuotes(tickers)

  const { segments, total } = useMemo(() => {
    const bySector: Record<string, number> = {}
    for (const ticker of tickers) {
      const quote = quotes?.[ticker]
      if (!quote) continue
      const value = quantityByTicker[ticker] * quote.price
      const sector = sectorFor(ticker)
      bySector[sector] = (bySector[sector] ?? 0) + value
    }
    const entries = Object.entries(bySector).sort(([, a], [, b]) => b - a)
    const total = entries.reduce((sum, [, v]) => sum + v, 0)
    const segments: DonutSegment[] = entries.map(([label, value], i) => ({
      label,
      value,
      colorClass: SECTOR_COLORS[i % SECTOR_COLORS.length],
    }))
    return { segments, total }
  }, [tickers, quantityByTicker, quotes])

  const formatUsd = (v: number) => `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`

  return (
    <div className="flex flex-col rounded-xl border border-[var(--border-primary)] bg-[var(--bg-card)] p-4 sm:p-5">
      <h2 className="text-sm font-bold text-[var(--text-primary)]">{t("portfolio_allocation_title")}</h2>

      {segments.length === 0 ? (
        <p className="mt-3 text-xs text-[var(--text-muted)]">{t("portfolio_perf_empty")}</p>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-6 py-4">
          <DonutChart segments={segments} size={188}>
            <span className="text-[11px] text-[var(--text-muted)]">{t("portfolio_allocation_total")}</span>
            <span className="font-mono-num text-xl font-bold text-[var(--text-primary)]">{formatUsd(total)}</span>
            <span className="text-[10px] text-[var(--text-ghost)]">{t("portfolio_allocation_groups", { count: segments.length })}</span>
          </DonutChart>

          <ul className="flex w-full flex-col gap-2.5">
            {segments.map((s) => {
              const pct = total > 0 ? (s.value / total) * 100 : 0
              return (
                <li key={s.label} className="flex flex-col gap-1">
                  <div className="flex items-center gap-2 text-xs">
                    <span className={`h-2 w-2 flex-none rounded-full ${s.colorClass}`} style={{ backgroundColor: "currentColor" }} />
                    <span className="min-w-0 flex-1 truncate text-[var(--text-secondary)]">{s.label}</span>
                    <span className="font-mono-num font-semibold text-[var(--text-primary)]">{formatUsd(s.value)}</span>
                    <span className="w-10 text-right font-mono-num text-[var(--text-muted)]">{pct.toFixed(0)}%</span>
                  </div>
                  <div className="h-1 overflow-hidden rounded-full bg-[var(--bg-hover)]">
                    <div className={`h-full rounded-full ${s.colorClass}`} style={{ width: `${pct}%`, backgroundColor: "currentColor" }} />
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
