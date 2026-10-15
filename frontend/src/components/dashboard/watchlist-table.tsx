import { useMemo, useState } from "react"
import { Search, Star, X } from "lucide-react"
import { useCompanies } from "@/hooks/use-companies"
import { useHistory, useQuotes } from "@/hooks/use-market"
import { useFavoriteTickers } from "@/hooks/use-favorite-tickers"
import { PriceChart } from "@/components/market/price-chart"
import { TickerAvatar } from "@/components/market/ticker-avatar"
import { sectorFor } from "@/lib/sectors"
import type { Company } from "@/types"
import { useTranslation } from "@/i18n/context"
import { cn } from "@/lib/utils"

export function TrendCell({ ticker }: { ticker: string }) {
  const { data: history } = useHistory(ticker, "1mo")
  return (
    <div className="h-8 w-20">
      <PriceChart data={history ?? []} height={32} sparkline />
    </div>
  )
}

function formatVolume(v: number | null): string {
  if (v === null) return "—"
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`
  return String(v)
}

// Watchlist card -- every tracked company (PROPOSAL.md's 15-company pilot
// set) as a flat, scannable row list, matching the reference dashboard's
// Watchlist panel (icon + name/sector, price, change, volume, trend
// sparkline). Replaces the earlier paginated/sortable report-style table:
// with only 15 rows total, pagination added friction without adding value.
// A row click still opens the ticker's detail modal.
export function WatchlistTable({ onSelect }: { onSelect: (ticker: string) => void }) {
  const { t } = useTranslation()
  const { data, isLoading, isError } = useCompanies()
  const [search, setSearch] = useState("")

  const all: Company[] = data ?? []
  const filtered = useMemo(
    () =>
      all.filter(
        (c) =>
          c.ticker.toLowerCase().includes(search.toLowerCase()) ||
          c.name.toLowerCase().includes(search.toLowerCase()),
      ),
    [all, search],
  )

  const { data: quotes } = useQuotes(filtered.map((c) => c.ticker))
  const { isFavorite, toggleFavorite } = useFavoriteTickers()

  return (
    <div className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-card)] p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-bold text-[var(--text-primary)]">{t("watchlist_title")}</h2>
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
            <button
              type="button"
              onClick={() => setSearch("")}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 hover:bg-[var(--bg-hover)]"
            >
              <X className="h-3 w-3 text-[var(--text-ghost)]" />
            </button>
          )}
        </div>
      </div>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-[var(--text-ghost)]">
              <th className="w-8 pb-2" />
              <th className="pb-2 font-medium">{t("watchlist_col_asset")}</th>
              <th className="pb-2 text-right font-medium">{t("company_table_price")}</th>
              <th className="hidden pb-2 text-right font-medium sm:table-cell">{t("watchlist_col_change")}</th>
              <th className="hidden pb-2 text-right font-medium md:table-cell">{t("watchlist_col_volume")}</th>
              <th className="hidden pb-2 pl-4 text-left font-medium lg:table-cell">{t("watchlist_col_trend")}</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-sm text-[var(--text-muted)]">
                  {t("company_list_loading")}
                </td>
              </tr>
            )}
            {isError && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-sm text-destructive">
                  {t("company_list_error")}
                </td>
              </tr>
            )}
            {!isLoading && !isError && filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-sm text-[var(--text-muted)]">
                  {t("company_list_empty")}
                </td>
              </tr>
            )}
            {filtered.map((company) => {
              const quote = quotes?.[company.ticker]
              const isUp = (quote?.change_pct ?? 0) >= 0
              return (
                <tr
                  key={company.ticker}
                  onClick={() => onSelect(company.ticker)}
                  className="cursor-pointer border-t border-[var(--border-primary)]/60 transition-colors hover:bg-[var(--bg-hover)]"
                >
                  <td className="py-2.5 pr-1">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        toggleFavorite(company.ticker)
                      }}
                      title={isFavorite(company.ticker) ? t("company_detail_favorite_remove") : t("company_detail_favorite_add")}
                      className="grid h-6 w-6 place-items-center rounded-full text-[var(--text-ghost)] hover:bg-[var(--bg-hover)]"
                    >
                      <Star
                        className={cn(
                          "h-3.5 w-3.5",
                          isFavorite(company.ticker) && "fill-[var(--accent-yellow)] text-[var(--accent-yellow)]",
                        )}
                      />
                    </button>
                  </td>
                  <td className="py-2.5">
                    <div className="flex items-center gap-2.5">
                      <TickerAvatar ticker={company.ticker} />
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-[var(--text-primary)]">
                          {company.name}
                        </div>
                        <div className="text-[11px] text-[var(--text-muted)]">{sectorFor(company.ticker)}</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-2.5 text-right font-mono-num text-sm text-[var(--text-primary)]">
                    {quote ? `$${quote.price.toFixed(2)}` : "—"}
                  </td>
                  <td className="hidden py-2.5 text-right sm:table-cell">
                    {quote?.change_pct !== null && quote?.change_pct !== undefined ? (
                      <span
                        className={cn(
                          "font-mono-num text-sm",
                          isUp ? "text-status-supported" : "text-status-broken",
                        )}
                      >
                        {isUp ? "+" : ""}
                        {quote.change_pct.toFixed(2)}%
                      </span>
                    ) : (
                      <span className="text-[var(--text-ghost)]">—</span>
                    )}
                  </td>
                  <td className="hidden py-2.5 text-right font-mono-num text-sm text-[var(--text-muted)] md:table-cell">
                    {formatVolume(quote?.volume ?? null)}
                  </td>
                  <td className="hidden py-2.5 pl-4 lg:table-cell">
                    <TrendCell ticker={company.ticker} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
