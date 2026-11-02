import { useState } from "react"
import { Sparkles, Trash2 } from "lucide-react"
import { Link, useSearchParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { RecordPurchaseDialog } from "@/components/portfolio/record-purchase-dialog"
import { HoldingsTable, type HeldCompany } from "@/components/portfolio/holdings-table"
import { HoldingDetail, useDeletePositionConfirm } from "@/components/portfolio/holding-detail"
import { PortfolioPerformanceCard } from "@/components/dashboard/portfolio-performance-card"
import { PortfolioAllocationCard } from "@/components/dashboard/portfolio-allocation-card"
import { TickerAvatar } from "@/components/market/ticker-avatar"
import { usePortfolioSummary } from "@/hooks/use-positions"
import { useTranslation } from "@/i18n/context"

export function PortfolioPage() {
  const { t } = useTranslation()
  const { data, isLoading, isError } = usePortfolioSummary()
  const deleteConfirm = useDeletePositionConfirm()
  const [searchParams, setSearchParams] = useSearchParams()
  const [recordOpen, setRecordOpen] = useState(false)

  // ?ticker= drives the modal, so a notification link opens that holding directly.
  const selectedTicker = searchParams.get("ticker")?.toUpperCase() ?? null
  const selected = data?.find((c): c is HeldCompany => c.ticker === selectedTicker && c.error == null)

  function openTicker(ticker: string) {
    setSearchParams((prev) => { const next = new URLSearchParams(prev); next.set("ticker", ticker); return next })
  }
  function closeModal() {
    setSearchParams((prev) => { const next = new URLSearchParams(prev); next.delete("ticker"); return next })
  }
  const askDelete = deleteConfirm.askDelete

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-[var(--text-primary)]">{t("portfolio_title")}</h1>
          <p className="max-w-2xl text-sm text-[var(--text-muted)]">{t("portfolio_intro")}</p>
        </div>
        <Link
          to="/agent"
          className="inline-flex flex-none items-center gap-1.5 rounded-full brand-gradient px-4 py-2.5 text-sm font-semibold text-white shadow-glow transition-opacity hover:opacity-90"
        >
          <Sparkles className="h-4 w-4" />
          {t("portfolio_ask_agent")}
        </Link>
      </div>

      {isLoading && <p className="text-sm text-[var(--text-muted)]">{t("portfolio_loading")}</p>}
      {isError && <p className="text-sm text-destructive">{t("portfolio_error")}</p>}
      {data && data.length === 0 && <p className="text-sm text-[var(--text-muted)]">{t("portfolio_empty")}</p>}

      {data && data.length > 0 && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]">
          <PortfolioPerformanceCard showPortfolioLink={false} />
          <PortfolioAllocationCard />
        </div>
      )}
      {/* Shown even when empty, so the first purchase can be recorded from here. */}
      {data && <HoldingsTable companies={data} onSelect={openTicker} onRecordPurchase={() => setRecordOpen(true)} />}

      <RecordPurchaseDialog open={recordOpen} onOpenChange={setRecordOpen} onRecorded={openTicker} />

      <Dialog open={!!selected} onOpenChange={(open) => !open && closeModal()}>
        {/* Pinned header, scrolling body -- same pattern as the dashboard's company modal. */}
        <DialogContent
          className="flex max-h-[85vh] max-w-4xl flex-col gap-0 overflow-hidden p-0"
          // Keep focus off the header delete button on open.
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          {selected && (
            <>
              <DialogHeader className="shrink-0 border-b border-[var(--border-primary)] px-6 py-4 pr-12">
                <div className="flex items-center justify-between gap-3">
                  <DialogTitle className="flex min-w-0 items-center gap-3">
                    <TickerAvatar ticker={selected.ticker} />
                    <span className="truncate">{selected.company_name}</span>
                    <span className="font-mono-num text-sm font-medium text-muted-foreground">{selected.ticker}</span>
                  </DialogTitle>
                  {/* One purchase: delete sits in the header. Several: each purchase row keeps its own. */}
                  {selected.positions.length === 1 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t("portfolio_delete_position_aria")}
                      onClick={() => askDelete(selected, selected.positions[0])}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </div>
              </DialogHeader>
              <div className="min-h-0 flex-1 overflow-y-auto p-6">
                <HoldingDetail company={selected} onDelete={(p) => askDelete(selected, p)} />
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {deleteConfirm.dialog}
    </div>
  )
}
