import { useMemo, useState } from "react"
import { Plus, Search, X } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/status-badge"
import { TrendCell } from "@/components/dashboard/watchlist-table"
import { TickerAvatar } from "@/components/market/ticker-avatar"
import { useQuotes } from "@/hooks/use-market"
import { useTranslation } from "@/i18n/context"
import { sectorFor } from "@/lib/sectors"
import { cn } from "@/lib/utils"
import type { PortfolioCompanySummary, PortfolioPosition, ReasonStatus } from "@/types"

export type HeldCompany = Extract<PortfolioCompanySummary, { error?: undefined }>

// The reason's state is its CURRENT status (passing / watch / failing), not
// "same as at purchase": the backend's still_true is false for an improvement
// too (Weakened -> Supported), which read as "no longer true".
const STATUS_SEVERITY: Record<ReasonStatus, number> = { Broken: 3, Weakened: 2, "Not enough data": 1, Supported: 0 }

export function worstStatus(statuses: (ReasonStatus | undefined)[]): ReasonStatus | null {
  const known = statuses.filter((s): s is ReasonStatus => !!s)
  return known.length ? known.reduce((a, b) => (STATUS_SEVERITY[b] > STATUS_SEVERITY[a] ? b : a)) : null
}

// No status to show has two different causes, so they get different labels:
// nothing was attached at purchase, or the attached reasons couldn't be
// re-checked (e.g. an old purchase saved before rules were frozen).
function MissingStatusBadge({ hasReasons }: { hasReasons: boolean }) {
  const { t } = useTranslation()
  const key = hasReasons ? "portfolio_status_unavailable" : "portfolio_status_no_reason"
  return (
    <span title={t(`${key}_hint`)}>
      <Badge variant="unknown">{t(key)}</Badge>
    </span>
  )
}

// A purchase's badge: the worst current status across all its reasons.
export function PositionStatus({ p }: { p: PortfolioPosition }) {
  const worst = worstStatus(p.reasons.map((r) => r.current_status))
  if (!worst) return <MissingStatusBadge hasReasons={p.reasons.length > 0} />
  return <StatusBadge status={worst} />
}

// Table cell: the worst current status across every reason of every purchase.
function CompanyStatus({ company }: { company: HeldCompany }) {
  const reasons = company.positions.flatMap((p) => p.reasons)
  const worst = worstStatus(reasons.map((r) => r.current_status))
  if (!worst) return <MissingStatusBadge hasReasons={reasons.length > 0} />
  return <StatusBadge status={worst} />
}

// Same look as the dashboard's watchlist table, limited to what the user
// holds; a row opens the holding's detail modal.
export function HoldingsTable({ companies, onSelect, onRecordPurchase, compact = false, selectedTicker = null }: {
  companies: PortfolioCompanySummary[]
  onSelect: (ticker: string) => void
  // Omit to hide the "Record a purchase" button.
  onRecordPurchase?: () => void
  // Narrow list beside a detail pane: asset, P&L and status only.
  compact?: boolean
  // Row to highlight as the one shown in the detail pane.
  selectedTicker?: string | null
}) {
  const { t } = useTranslation()
  const [search, setSearch] = useState("")
  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return companies.filter((c) => c.ticker.toLowerCase().includes(q) || (c.company_name ?? "").toLowerCase().includes(q))
  }, [companies, search])
  const { data: quotes } = useQuotes(filtered.map((c) => c.ticker))
  const columns = compact ? 3 : 8

  return (
    <div className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-card)] p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-bold text-[var(--text-primary)]">
          {t("holdings_title")} <span className="font-normal text-[var(--text-muted)]">— {companies.length}</span>
        </h2>
        <div className="flex items-center gap-2">
        <div className="relative w-48">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-ghost)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("company_search_placeholder")}
            className="h-8 w-full rounded-lg border border-[var(--border-primary)] bg-[var(--bg-input)] pl-8 pr-7 text-xs text-[var(--text-primary)] outline-none transition-colors focus-visible:border-primary"
          />
          {search && (
            <button type="button" onClick={() => setSearch("")} className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 hover:bg-[var(--bg-hover)]">
              <X className="h-3 w-3 text-[var(--text-ghost)]" />
            </button>
          )}
        </div>
        {onRecordPurchase && (
          <Button type="button" size="sm" className="gap-1.5" onClick={onRecordPurchase}>
            <Plus className="h-3.5 w-3.5" />
            {t("record_purchase_title")}
          </Button>
        )}
        </div>
      </div>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-[var(--text-ghost)]">
              <th className="pb-2 font-medium">{t("watchlist_col_asset")}</th>
              {!compact && <th className="hidden pb-2 text-right font-medium sm:table-cell">{t("holdings_col_quantity")}</th>}
              {!compact && <th className="hidden pb-2 text-right font-medium sm:table-cell">{t("company_detail_total_invested")}</th>}
              {!compact && <th className="pb-2 text-right font-medium">{t("company_table_price")}</th>}
              {!compact && <th className="hidden pb-2 text-right font-medium md:table-cell">{t("watchlist_col_change")}</th>}
              <th className="pb-2 text-right font-medium">{t("portfolio_pnl_since_purchase")}</th>
              <th className={cn("pb-2 pl-4 font-medium", !compact && "hidden md:table-cell")}>{t("holdings_col_status")}</th>
              {!compact && <th className="hidden pb-2 pl-4 font-medium lg:table-cell">{t("watchlist_col_trend")}</th>}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={columns} className="py-6 text-center text-sm text-[var(--text-muted)]">{t("company_list_empty")}</td></tr>
            )}
            {filtered.map((company) => {
              if (company.error != null) {
                return (
                  <tr key={company.ticker} className="border-t border-[var(--border-primary)]/60">
                    <td colSpan={columns} className="py-2.5 text-sm text-destructive">{company.ticker}: {company.error}</td>
                  </tr>
                )
              }
              const quote = quotes?.[company.ticker]
              const shares = company.positions.reduce((sum, p) => sum + p.quantity, 0)
              const cost = company.positions.reduce((sum, p) => sum + p.quantity * p.purchase_price, 0)
              const pnlKnown = company.positions.every((p) => p.unrealized_pnl !== null)
              const pnl = company.positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0)
              const pnlPct = cost > 0 ? (pnl / cost) * 100 : null
              const price = quote?.price ?? company.positions[0]?.current_price ?? null
              const isUp = (quote?.change_pct ?? 0) >= 0
              return (
                <tr
                  key={company.ticker}
                  onClick={() => onSelect(company.ticker)}
                  aria-selected={compact ? selectedTicker === company.ticker : undefined}
                  className={cn(
                    "cursor-pointer border-t border-[var(--border-primary)]/60 transition-colors hover:bg-[var(--bg-hover)]",
                    selectedTicker === company.ticker && "bg-primary/10 hover:bg-primary/10",
                  )}
                >
                  <td className={cn("py-2.5", compact && "pl-2", selectedTicker === company.ticker && "shadow-[inset_3px_0_0_hsl(var(--primary))]")}>
                    <div className="flex items-center gap-2.5">
                      <TickerAvatar ticker={company.ticker} />
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-[var(--text-primary)]">{company.company_name}</div>
                        <div className="text-[11px] text-[var(--text-muted)]">{company.ticker} · {sectorFor(company.ticker)}</div>
                      </div>
                    </div>
                  </td>
                  {!compact && <>
                  <td className="hidden py-2.5 text-right font-mono-num text-sm text-[var(--text-primary)] sm:table-cell">{shares}</td>
                  {/* What was paid in total, with the average price per share underneath. */}
                  <td className="hidden py-2.5 text-right sm:table-cell">
                    <div className="font-mono-num text-sm text-[var(--text-primary)]">${cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                    {shares > 0 && (
                      <div className="text-[11px] text-[var(--text-muted)]">
                        {t("holdings_avg_price", { price: (cost / shares).toFixed(2) })}
                      </div>
                    )}
                  </td>
                  <td className="py-2.5 text-right font-mono-num text-sm text-[var(--text-primary)]">{price !== null ? `$${price.toFixed(2)}` : "—"}</td>
                  <td className="hidden py-2.5 text-right md:table-cell">
                    {quote?.change_pct != null ? (
                      <span className={cn("font-mono-num text-sm", isUp ? "text-status-supported" : "text-status-broken")}>
                        {isUp ? "+" : ""}{quote.change_pct.toFixed(2)}%
                      </span>
                    ) : <span className="text-[var(--text-ghost)]">—</span>}
                  </td>
                  </>}
                  <td className="py-2.5 text-right">
                    {pnlKnown ? (
                      <span className={cn("font-mono-num text-sm", pnl >= 0 ? "text-status-supported" : "text-status-broken")}>
                        {pnl >= 0 ? "+" : "−"}${Math.abs(pnl).toFixed(2)}
                        {pnlPct !== null && <span className="ml-1 text-xs opacity-80">({pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(1)}%)</span>}
                      </span>
                    ) : <span className="text-[var(--text-ghost)]">—</span>}
                  </td>
                  <td className={cn("py-2.5 pl-4", !compact && "hidden md:table-cell")}><CompanyStatus company={company} /></td>
                  {!compact && <td className="hidden py-2.5 pl-4 lg:table-cell"><TrendCell ticker={company.ticker} /></td>}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
