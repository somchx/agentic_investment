import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { Sparkles } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { CompanyDetailHeader } from "@/components/dashboard/company-detail-header"
import { PortfolioPerformanceCard } from "@/components/dashboard/portfolio-performance-card"
import { WatchlistTable } from "@/components/dashboard/watchlist-table"
import { PortfolioAllocationCard } from "@/components/dashboard/portfolio-allocation-card"
import { RecordPurchaseForm } from "@/components/dashboard/record-purchase-form"
import { DataFreshnessStatus } from "@/components/dashboard/data-freshness-status"
import { InvestigationPanel } from "@/components/dashboard/investigation-panel"
import { useAuth } from "@/hooks/use-auth"
import { useCompanies } from "@/hooks/use-companies"
import { useReport } from "@/hooks/use-report"
import { useDeleteReason, useReasons } from "@/hooks/use-reasons"
import { useTranslation } from "@/i18n/context"
import { usePortfolioSummary } from "@/hooks/use-positions"
import { HoldingsTable, type HeldCompany } from "@/components/portfolio/holdings-table"
import { HoldingDetail, HoldingTitle, useDeletePositionConfirm } from "@/components/portfolio/holding-detail"

function CompanyDetail({ ticker }: { ticker: string }) {
  const { t } = useTranslation()
  const { data: report, isLoading: reportLoading, isError: reportError } = useReport(ticker)
  const { data: reasons } = useReasons(ticker)
  const deleteReason = useDeleteReason()

  return (
    <div className="flex flex-col gap-6">
      <CompanyDetailHeader ticker={ticker} />

      {reportLoading && <p className="text-sm text-muted-foreground">{t("dashboard_report_loading")}</p>}
      {reportError && (
        <p className="text-sm text-destructive">{t("dashboard_report_error", { ticker })}</p>
      )}

      {report && report.reasons.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("dashboard_no_reasons", { ticker })}</p>
      )}

      <div id="investigation-panel">
        <InvestigationPanel
          ticker={ticker}
          reasons={report?.reasons ?? []}
          dataFreshness={report?.data_freshness}
          reasonsMeta={reasons}
          onDeleteReason={(key) => deleteReason.mutate(key)}
        />
      </div>

      <RecordPurchaseForm ticker={ticker} reasons={report?.reasons ?? []} />
    </div>
  )
}

export function DashboardPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { data: companies } = useCompanies()
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null)
  const [holdingsOpen, setHoldingsOpen] = useState(false)
  const { data: holdings } = usePortfolioSummary()
  const [activeTicker, setActiveTicker] = useState<string | null>(null)
  const deleteConfirm = useDeletePositionConfirm()
  const heldCompanies = (holdings ?? []).filter((c): c is HeldCompany => c.error == null)
  // The picked holding, or the first one -- so the detail pane is never empty
  // when the modal opens (or after the shown holding is deleted).
  const activeHolding = heldCompanies.find((c) => c.ticker === activeTicker) ?? heldCompanies[0]

  // ?holding=TICKER (notifications, old /portfolio links) opens the holdings
  // modal on that holding; an empty value just opens it.
  useEffect(() => {
    const holding = searchParams.get("holding")
    if (holding === null) return
    setActiveTicker(holding ? holding.toUpperCase() : null)
    setHoldingsOpen(true)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete("holding")
      return next
    }, { replace: true })
  }, [searchParams, setSearchParams])

  // Forget the pick on close, so the next open starts from the first holding.
  // (Done in the close handler, not an effect: an effect would also fire on the
  // first render and wipe a ?holding= pick.)
  function setHoldingsModalOpen(open: boolean) {
    setHoldingsOpen(open)
    if (!open) setActiveTicker(null)
  }


  // A link from elsewhere (e.g. the Portfolio page's "View details") can
  // deep-link straight into a company's detail modal via ?ticker=.
  useEffect(() => {
    if (selectedTicker || !companies || companies.length === 0) return
    const fromUrl = searchParams.get("ticker")?.toUpperCase()
    const match = fromUrl && companies.find((c) => c.ticker === fromUrl)
    if (match) setSelectedTicker(match.ticker)
  }, [companies, selectedTicker, searchParams])

  const selectedCompany = companies?.find((c) => c.ticker === selectedTicker)

  function openTicker(ticker: string) {
    setSelectedTicker(ticker)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set("ticker", ticker)
      return next
    })
  }

  function closeModal() {
    setSelectedTicker(null)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete("ticker")
      return next
    })
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs text-[var(--text-muted)]">{t("dashboard_welcome_back")}</p>
          <h1 className="text-base font-bold text-[var(--text-primary)]">{user?.full_name ?? ""}</h1>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-3">
          <DataFreshnessStatus />
          <Link
            to="/agent"
            className="inline-flex flex-none items-center gap-1.5 rounded-full brand-gradient px-4 py-2.5 text-sm font-semibold text-white shadow-glow transition-opacity hover:opacity-90"
          >
            <Sparkles className="h-4 w-4" />
            {t("dashboard_ai_assistant")}
          </Link>
        </div>
      </div>

      {/* Same pairing as the Portfolio page: performance with allocation beside it. */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]">
        <PortfolioPerformanceCard onViewPortfolio={() => setHoldingsOpen(true)} />
        <PortfolioAllocationCard />
      </div>

      <WatchlistTable onSelect={openTicker} />

      {/* "View portfolio": holdings list on the left, the picked holding's full
          detail on the right; the first holding is shown as soon as it opens. */}
      <Dialog open={holdingsOpen} onOpenChange={setHoldingsModalOpen}>
        <DialogContent
          className="flex h-[88vh] max-w-[min(96vw,1400px)] flex-col gap-0 overflow-hidden p-0"
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <DialogHeader className="shrink-0 border-b border-[var(--border-primary)] px-6 py-4 pr-12">
            <DialogTitle>{t("portfolio_title")}</DialogTitle>
          </DialogHeader>
          <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(340px,2fr)_3fr]">
            <div className="min-h-0 overflow-y-auto border-b border-[var(--border-primary)] p-4 lg:border-b-0 lg:border-r">
              {holdings && (
                <HoldingsTable
                  compact
                  companies={holdings}
                  selectedTicker={activeHolding?.ticker ?? null}
                  onSelect={setActiveTicker}
                />
              )}
            </div>
            <div className="min-h-0 overflow-y-auto px-4 pb-4 sm:px-6 sm:pb-6">
              {activeHolding ? (
                <div className="flex flex-col gap-4">
                  {/* Company name stays pinned while the detail scrolls under it. */}
                  <div className="sticky top-0 z-10 -mx-4 border-b border-[var(--border-primary)] bg-[var(--bg-card)] px-4 py-3 sm:-mx-6 sm:px-6">
                    <HoldingTitle company={activeHolding} onDelete={(p) => deleteConfirm.askDelete(activeHolding, p)} />
                  </div>
                  <HoldingDetail key={activeHolding.ticker} company={activeHolding} onDelete={(p) => deleteConfirm.askDelete(activeHolding, p)} />
                </div>
              ) : (
                <p className="py-12 text-center text-sm text-[var(--text-muted)]">{t("portfolio_empty")}</p>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
      {deleteConfirm.dialog}

      <Dialog open={!!selectedTicker} onOpenChange={(open) => !open && closeModal()}>
        {/* Header sits outside the scroll area so the company name stays pinned while the body scrolls. */}
        <DialogContent className="flex max-h-[85vh] max-w-4xl flex-col gap-0 overflow-hidden p-0">
          {selectedTicker && (
            <>
              <DialogHeader className="shrink-0 border-b border-[var(--border-primary)] px-6 py-4 pr-12">
                <DialogTitle>
                  {selectedCompany?.name ?? selectedTicker}{" "}
                  <span className="font-mono-num text-sm font-medium text-muted-foreground">
                    {selectedTicker}
                  </span>
                </DialogTitle>
              </DialogHeader>
              <div className="min-h-0 flex-1 overflow-y-auto p-6">
                <CompanyDetail ticker={selectedTicker} />
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
