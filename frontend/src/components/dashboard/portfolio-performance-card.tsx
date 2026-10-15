import { useMemo, useState } from "react"
import { ArrowUpRight } from "lucide-react"
import { PriceChart } from "@/components/market/price-chart"
import { usePortfolioSummary } from "@/hooks/use-positions"
import { useQuotes } from "@/hooks/use-market"
import { usePortfolioHistory } from "@/hooks/use-portfolio-history"
import { useTranslation } from "@/i18n/context"
import { purchaseTotals } from "@/lib/portfolio-totals"
import { cn } from "@/lib/utils"
import type { HistoryRange } from "@/types"

const RANGES: { value: HistoryRange; labelKey: string }[] = [
  { value: "1d", labelKey: "range_1d" },
  { value: "1mo", labelKey: "range_1m" },
  { value: "1y", labelKey: "range_1y" },
  { value: "5y", labelKey: "range_5y" },
  { value: "max", labelKey: "range_max" },
]

const viewAllClass =
  "inline-flex flex-none items-center gap-1 rounded-lg border border-[var(--border-primary)] px-2.5 py-1.5 text-xs font-semibold text-[var(--text-faint)] transition-colors hover:border-primary/50 hover:text-primary"

// `onViewPortfolio`: opens the dashboard's holdings modal (no button without it).
export function PortfolioPerformanceCard({ showPortfolioLink = true, onViewPortfolio }: {
  showPortfolioLink?: boolean
  onViewPortfolio?: () => void
}) {
  const { t } = useTranslation()
  const [range, setRange] = useState<HistoryRange>("1y")
  const { data: summary } = usePortfolioSummary()

  const quantityByTicker = useMemo(() => {
    const map: Record<string, number> = {}
    for (const company of summary ?? []) {
      if ("error" in company) continue
      for (const p of company.positions) {
        map[company.ticker] = (map[company.ticker] ?? 0) + p.quantity
      }
    }
    return map
  }, [summary])

  const heldTickers = Object.keys(quantityByTicker)
  const { data: quotes } = useQuotes(heldTickers)
  const { data: history } = usePortfolioHistory(quantityByTicker, range)

  const totals = useMemo(() => {
    let value = 0
    let dailyComplete = !!summary && !summary.some(company => "error" in company)
    let dayGain = 0
    let dayLow = 0
    let dayHigh = 0
    for (const ticker of heldTickers) {
      const qty = quantityByTicker[ticker]
      const quote = quotes?.[ticker]
      if (!quote) { dailyComplete = false; continue }
      if (quote.change === null) dailyComplete = false
      value += qty * quote.price
      dayGain += qty * (quote.change ?? 0)
      dayLow += qty * (quote.day_low ?? quote.price)
      dayHigh += qty * (quote.day_high ?? quote.price)
    }
    const dayGainPct = value - dayGain !== 0 ? (dayGain / (value - dayGain)) * 100 : 0
    return { value, dailyComplete, dayGain, dayGainPct, dayLow, dayHigh, ...purchaseTotals(summary) }
  }, [heldTickers, quantityByTicker, quotes, summary])

  if (heldTickers.length === 0 && !summary?.some(company => "error" in company)) {
    return (
      <div className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-card)] p-6 text-center text-sm text-[var(--text-muted)]">
        {t("portfolio_perf_empty")}
      </div>
    )
  }

  const isUp = totals.dayGain >= 0

  return (
    <div className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-card)] p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 className="text-base font-bold text-[var(--text-primary)]">{t("portfolio_perf_title")}</h2>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex gap-1 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-hover)] p-0.5">
            {RANGES.map((r) => (
              <button
                key={r.value}
                type="button"
                onClick={() => setRange(r.value)}
                className={cn(
                  "rounded-md px-2.5 py-1 text-xs font-semibold transition-colors",
                  range === r.value
                    ? "bg-primary/15 text-primary"
                    : "text-[var(--text-faint)] hover:text-[var(--text-primary)]",
                )}
              >
                {t(r.labelKey)}
              </button>
            ))}
          </div>
          {showPortfolioLink && onViewPortfolio && (
            <button type="button" onClick={onViewPortfolio} className={viewAllClass}>
              {t("portfolio_perf_view_all")}
              <ArrowUpRight className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <p className="mt-1 text-xs text-[var(--text-muted)]">{t("portfolio_perf_comparison_hint")}</p>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,260px)_1fr]">
        <div className="flex flex-col gap-4">
          <div>
            <div className="text-xs text-[var(--text-muted)]">{t("portfolio_perf_value_label")}</div>
            <div className="font-mono-num text-3xl font-extrabold text-[var(--text-primary)]">
              {totals.purchaseValue === null ? "—" : `$${totals.purchaseValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            </div>
          </div>

          <div className="rounded-lg bg-[var(--bg-hover)] p-3">
            <div className="text-xs text-[var(--text-muted)]">{t("portfolio_pnl_since_purchase")}</div>
            <div className={cn("font-mono-num text-lg font-semibold", totals.purchaseGain === null ? "text-[var(--text-muted)]" : totals.purchaseGain >= 0 ? "text-status-supported" : "text-status-broken")}>
              {totals.purchaseGain === null ? "—" : `${totals.purchaseGain >= 0 ? "+" : "-"}$${Math.abs(totals.purchaseGain).toFixed(2)}`}
              {totals.purchaseGainPct !== null && ` (${totals.purchaseGainPct >= 0 ? "+" : ""}${totals.purchaseGainPct.toFixed(2)}%)`}
            </div>
            <p className="mt-1 text-xs text-[var(--text-faint)]">{t(totals.purchaseGain === null ? "portfolio_perf_incomplete" : "portfolio_perf_purchase_hint")}</p>
          </div>

          <div className="rounded-lg bg-[var(--bg-hover)] p-3">
            <div className="text-xs text-[var(--text-muted)]">{t("portfolio_perf_today_gain_label")}</div>
            <div
              className={cn(
                "font-mono-num text-lg font-semibold",
                !totals.dailyComplete ? "text-[var(--text-muted)]" : isUp ? "text-status-supported" : "text-status-broken",
              )}
            >
              {totals.dailyComplete ? `${isUp ? "+" : "-"}$${Math.abs(totals.dayGain).toFixed(2)} (${totals.dayGainPct >= 0 ? "+" : ""}${totals.dayGainPct.toFixed(2)}%)` : "—"}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-[var(--bg-hover)] p-3">
              <div className="text-xs text-[var(--text-muted)]">{t("portfolio_perf_day_low")}</div>
              <div className="font-mono-num text-sm font-semibold text-[var(--text-primary)]">
                {totals.dailyComplete ? `$${totals.dayLow.toFixed(2)}` : "—"}
              </div>
            </div>
            <div className="rounded-lg bg-[var(--bg-hover)] p-3">
              <div className="text-xs text-[var(--text-muted)]">{t("portfolio_perf_day_high")}</div>
              <div className="font-mono-num text-sm font-semibold text-[var(--text-primary)]">
                {totals.dailyComplete ? `$${totals.dayHigh.toFixed(2)}` : "—"}
              </div>
            </div>
          </div>
        </div>

        <PriceChart data={history ?? []} height={240} />
      </div>
    </div>
  )
}
