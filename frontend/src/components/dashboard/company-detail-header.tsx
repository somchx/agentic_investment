import { useState } from "react"
import { Loader2, Share2, Star } from "lucide-react"
import { PriceChart } from "@/components/market/price-chart"
import { RiskMeter, riskLevelFor } from "@/components/dashboard/risk-meter"
import { useHistory, useQuote } from "@/hooks/use-market"
import { usePositions } from "@/hooks/use-positions"
import { useReport } from "@/hooks/use-report"
import { useFavoriteTickers } from "@/hooks/use-favorite-tickers"
import { sectorFor } from "@/lib/sectors"
import { useTranslation } from "@/i18n/context"
import { cn } from "@/lib/utils"
import type { HistoryRange } from "@/types"

const RANGES: { value: HistoryRange; labelKey: string }[] = [
  { value: "1d", labelKey: "range_1d" },
  { value: "1mo", labelKey: "range_1m" },
  { value: "3mo", labelKey: "range_3m" },
  { value: "1y", labelKey: "range_1y" },
  { value: "5y", labelKey: "range_5y" },
  { value: "max", labelKey: "range_max" },
]

function StatTile({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] text-[var(--text-muted)]">{label}</span>
      <span className={cn("font-mono-num text-sm font-semibold text-[var(--text-primary)]", valueClass)}>
        {value}
      </span>
    </div>
  )
}

function formatVolume(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—"
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`
  return String(v)
}

// Price header + chart + "Your Position" stat tiles for the ticker detail
// modal, matching the reference dashboards' stock-detail layout -- but
// built entirely on this project's own real data: portfolio positions,
// SEC-evidence-derived risk level, and Yahoo Finance's free quote fields.
// Deliberately NOT included: Market Cap and P/E Ratio, shown in the
// reference screenshots -- Yahoo's free chart endpoint (the only quote
// source this project uses, no API key) doesn't expose either; the
// endpoint that does (quoteSummary/quote) now requires an auth "crumb"
// this project has no session for. Shown fields are the ones genuinely
// available, not approximated or invented to fill the layout.
export function CompanyDetailHeader({ ticker, reasonsAnchorId = "reason-checks" }: { ticker: string; reasonsAnchorId?: string }) {
  const { t } = useTranslation()
  const [range, setRange] = useState<HistoryRange>("3mo")
  const [copied, setCopied] = useState(false)
  const { data: quote } = useQuote(ticker)
  const { data: history } = useHistory(ticker, range)
  const { data: positions } = usePositions(ticker)
  const { data: report, refetch: recheckReasons, isFetching: checkingReasons } = useReport(ticker)
  const { isFavorite, toggleFavorite } = useFavoriteTickers()

  const holding =
    positions && positions.length > 0
      ? positions.reduce(
          (acc, p) => ({
            shares: acc.shares + p.quantity,
            cost: acc.cost + p.quantity * p.purchase_price,
          }),
          { shares: 0, cost: 0 },
        )
      : null

  const avgBuyPrice = holding && holding.shares > 0 ? holding.cost / holding.shares : null
  const currentValue = holding && quote ? holding.shares * quote.price : null
  const pnl = currentValue !== null && holding ? currentValue - holding.cost : null
  const pnlPct = pnl !== null && holding && holding.cost > 0 ? (pnl / holding.cost) * 100 : null
  const riskLevel = riskLevelFor(report?.reasons ?? [])
  const favorite = isFavorite(ticker)

  async function handleShare() {
    const url = `${window.location.origin}${window.location.pathname}?ticker=${ticker}`
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard access can be blocked (permissions, non-HTTPS context);
      // failing silently here just means the user re-copies manually.
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-card)] p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
            {sectorFor(ticker)}
          </div>
        </div>
        <div className="flex flex-none items-center gap-1.5">
          <button
            type="button"
            onClick={handleShare}
            title={t("company_detail_share")}
            className="grid h-8 w-8 place-items-center rounded-full text-[var(--text-faint)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
          >
            <Share2 className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => toggleFavorite(ticker)}
            title={favorite ? t("company_detail_favorite_remove") : t("company_detail_favorite_add")}
            className="grid h-8 w-8 place-items-center rounded-full text-[var(--text-faint)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <Star className={cn("h-4 w-4", favorite && "fill-[var(--accent-yellow)] text-[var(--accent-yellow)]")} />
          </button>
        </div>
      </div>
      {copied && <p className="-mt-2 text-xs text-status-supported">{t("company_detail_share_copied")}</p>}

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          {quote ? (
            <>
              <div className="font-mono-num text-3xl font-extrabold text-[var(--text-primary)]">
                ${quote.price.toFixed(2)}
              </div>
              {quote.change !== null && quote.change_pct !== null && (
                <div
                  className={cn(
                    "mt-1 font-mono-num text-sm font-medium",
                    quote.change >= 0 ? "text-status-supported" : "text-status-broken",
                  )}
                >
                  {quote.change >= 0 ? "+" : ""}
                  {quote.change.toFixed(2)} ({quote.change >= 0 ? "+" : ""}
                  {quote.change_pct.toFixed(2)}%)
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-[var(--text-muted)]">{t("company_detail_price_loading")}</div>
          )}
        </div>

        <div className="flex gap-1 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-hover)] p-0.5">
          {RANGES.map((r) => (
            <button
              key={r.value}
              type="button"
              onClick={() => setRange(r.value)}
              className={cn(
                "rounded-md px-2 py-1 text-xs font-semibold transition-colors",
                range === r.value
                  ? "bg-primary/15 text-primary"
                  : "text-[var(--text-faint)] hover:text-[var(--text-primary)]",
              )}
            >
              {t(r.labelKey)}
            </button>
          ))}
        </div>
      </div>

      <button
        type="button"
        onClick={() => {
          // Re-run the mechanical reason check (same zero-AI evaluation the screener uses)
          // and jump to the per-reason verdicts below.
          if (!checkingReasons) void recheckReasons()
          document.getElementById(reasonsAnchorId)?.scrollIntoView({ behavior: "smooth", block: "start" })
        }}
        // Not `disabled` while checking: disabling the focused button drops focus, and the
        // dialog's focus trap then refocuses its first control, scrolling back to the top.
        aria-busy={checkingReasons}
        className="inline-flex w-fit items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/15 aria-busy:opacity-60"
      >
        {checkingReasons && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
        {t("company_detail_still_good_position")}
      </button>

      <PriceChart data={history ?? []} height={180} />

      <div className="grid grid-cols-3 gap-3 border-t border-[var(--border-primary)] pt-3">
        <StatTile label={t("company_detail_volume")} value={formatVolume(quote?.volume)} />
        <StatTile
          label={t("company_detail_52w_high")}
          value={quote?.fifty_two_week_high !== undefined && quote?.fifty_two_week_high !== null ? `$${quote.fifty_two_week_high.toFixed(2)}` : "—"}
        />
        <StatTile
          label={t("company_detail_52w_low")}
          value={quote?.fifty_two_week_low !== undefined && quote?.fifty_two_week_low !== null ? `$${quote.fifty_two_week_low.toFixed(2)}` : "—"}
        />
      </div>

      <RiskMeter level={riskLevel} />

      {holding && holding.shares > 0 && (
        <div className="grid grid-cols-2 gap-3 border-t border-[var(--border-primary)] pt-3 sm:grid-cols-5">
          <StatTile label={t("company_detail_total_shares")} value={holding.shares.toString()} />
          <StatTile
            label={t("company_detail_avg_buy_price")}
            value={avgBuyPrice !== null ? `$${avgBuyPrice.toFixed(2)}` : "—"}
          />
          <StatTile label={t("company_detail_total_invested")} value={`$${holding.cost.toFixed(2)}`} />
          <StatTile
            label={t("company_detail_current_value")}
            value={currentValue !== null ? `$${currentValue.toFixed(2)}` : "—"}
          />
          <StatTile
            label={t("company_detail_pnl")}
            value={pnl !== null ? `${pnl >= 0 ? "+" : ""}$${pnl.toFixed(2)} (${pnlPct !== null ? (pnlPct >= 0 ? "+" : "") + pnlPct.toFixed(1) : "—"}%)` : "—"}
            valueClass={pnl !== null ? (pnl >= 0 ? "text-status-supported" : "text-status-broken") : undefined}
          />
        </div>
      )}
    </div>
  )
}
