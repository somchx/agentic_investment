import { useState } from "react"
import { Trash2 } from "lucide-react"
import { StatusBadge } from "@/components/status-badge"
import { Button } from "@/components/ui/button"
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import { ThesisPanel } from "@/components/portfolio/thesis-panel"
import { ThesisRevalidation } from "@/components/portfolio/thesis-revalidation"
import { CompanyAiSummary } from "@/components/portfolio/company-ai-summary"
import { CompanyDetailHeader } from "@/components/dashboard/company-detail-header"
import { ThresholdGauge } from "@/components/dashboard/threshold-gauge"
import { PositionStatus, type HeldCompany } from "@/components/portfolio/holdings-table"
import { TickerAvatar } from "@/components/market/ticker-avatar"
import { useDeletePosition } from "@/hooks/use-positions"
import { useTranslation } from "@/i18n/context"
import { getApiErrorMessage } from "@/api/client"
import { cn } from "@/lib/utils"
import type { ComparisonOp, PortfolioPosition, PositionReason } from "@/types"

// One holding's full detail (price/risk header, each purchase with its reasons
// and thesis tools, AI Summary) -- shared by the Portfolio page's modal and the
// dashboard's holdings modal.

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

// One reason of a purchase: what it was at purchase vs. now, on the threshold gauge.
function PurchaseReasonRow({ r }: { r: PositionReason }) {
  const { t, tReason } = useTranslation()
  const snap = r.reason_snapshot
  if (!snap) return null
  const statusLabel = (status: string) => t("status_" + status.toLowerCase().replace(/ /g, "_"))
  const changed = r.current_status && snap.status_at_purchase !== r.current_status
  const hasGauge =
    typeof snap.threshold === "number" && typeof snap.comparison === "string" &&
    (snap.computed_value_at_purchase != null || r.current_computed_value != null)
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="text-xs text-[var(--text-muted)]">
          {t("portfolio_bought_for", {
            description: tReason(r.reason_key, snap.description),
            status: statusLabel(snap.status_at_purchase),
          })}
        </div>
        {r.current_status && (
          <span className="inline-flex flex-col items-end gap-0.5">
            <StatusBadge status={r.current_status} />
            {changed && <span className="text-[10px] text-[var(--text-muted)]">{t("portfolio_status_changed_since_purchase")}</span>}
          </span>
        )}
      </div>
      {hasGauge && (
        <div className="max-w-md">
          <ThresholdGauge
            threshold={snap.threshold as number}
            comparison={snap.comparison as ComparisonOp}
            rows={[
              ...(snap.computed_value_at_purchase != null
                ? [{ label: t("portfolio_value_at_purchase").replace(":", ""), value: snap.computed_value_at_purchase, status: snap.status_at_purchase }]
                : []),
              ...(r.current_computed_value != null
                ? [{ label: t("portfolio_value_now").replace(":", ""), value: r.current_computed_value, status: r.current_status ?? "Not enough data" }]
                : []),
            ]}
          />
        </div>
      )}
    </div>
  )
}

/** What each holding card used to show: every purchase (summary, P&L,
 * reason gauge, thesis tools) plus the company's AI Summary. Now the body of
 * the holding modal. */
export function HoldingDetail({ company, onDelete }: { company: HeldCompany; onDelete: (p: PortfolioPosition) => void }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-4">
      {/* Same price/chart/risk/position header as the dashboard's company modal. */}
      <CompanyDetailHeader ticker={company.ticker} reasonsAnchorId={`reason-checks-${company.ticker}`} />
      <div className="flex flex-col gap-3">
        {company.positions.map((p) => (
          <div
            key={p.id}
            className="flex flex-col gap-3 rounded-lg bg-[var(--bg-hover)] p-3 sm:p-4"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="font-mono-num text-sm font-semibold text-[var(--text-primary)]">
                {t("portfolio_position_summary", {
                  quantity: p.quantity,
                  price: p.purchase_price,
                  date: p.purchase_date,
                })}
              </div>
              <div className="flex items-center gap-2">
                <PositionStatus p={p} />
                {company.positions.length > 1 && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={t("portfolio_delete_position_aria")}
                    onClick={() => onDelete(p)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                )}
              </div>
            </div>

            {p.current_price !== null && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <StatTile label={t("portfolio_current_price")} value={`$${p.current_price.toFixed(2)}`} />
                {p.unrealized_pnl !== null && (
                  <StatTile
                    label={t("portfolio_pnl_since_purchase")}
                    value={`${p.unrealized_pnl >= 0 ? "+" : ""}${p.unrealized_pnl.toFixed(2)} (${
                      p.unrealized_pnl_pct !== null && p.unrealized_pnl_pct >= 0 ? "+" : ""
                    }${p.unrealized_pnl_pct?.toFixed(1)}%)`}
                    valueClass={p.unrealized_pnl >= 0 ? "text-status-supported" : "text-status-broken"}
                  />
                )}
              </div>
            )}

            {p.reasons.length > 0 ? (
              <div className="flex flex-col gap-3 border-t border-[var(--border-primary)]/60 pt-3">
                {p.reasons.map((r) => <PurchaseReasonRow key={r.reason_key} r={r} />)}
              </div>
            ) : (
              <div className="border-t border-[var(--border-primary)]/60 pt-3 text-xs text-[var(--text-muted)]">
                {t("portfolio_no_reason")}
              </div>
            )}

            {p.reasons.length > 0 && <ThesisRevalidation positionId={p.id} ticker={company.ticker} />}

            {p.thesis && <ThesisPanel positionId={p.id} thesis={p.thesis} reasons={p.reasons} />}
          </div>
        ))}
      </div>
      <CompanyAiSummary ticker={company.ticker} />
    </div>
  )
}

// Delete-a-purchase confirmation, shared by every place that shows holdings.
// Render `dialog` once; call `askDelete` from any delete button.
export function useDeletePositionConfirm() {
  const { t } = useTranslation()
  const deletePosition = useDeletePosition()
  const [deleteTarget, setDeleteTarget] = useState<(PortfolioPosition & { company_name: string }) | null>(null)

  function askDelete(company: HeldCompany, p: PortfolioPosition) {
    deletePosition.reset()
    setDeleteTarget({ ...p, company_name: company.company_name })
  }

  const dialog = (
      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => { if (!open && !deletePosition.isPending) setDeleteTarget(null) }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("portfolio_delete_title")}</AlertDialogTitle>
          <AlertDialogDescription>{t("portfolio_delete_description")}</AlertDialogDescription>
        </AlertDialogHeader>
        {deleteTarget && (
          <div className="rounded-md border border-[var(--border-primary)] bg-[var(--bg-hover)] p-3 text-sm">
            <p className="font-semibold">{deleteTarget.company_name} <span className="font-mono-num text-xs text-muted-foreground">{deleteTarget.ticker}</span></p>
            <p className="mt-0.5 font-mono-num text-xs text-[var(--text-muted)]">
              {t("portfolio_position_summary", { quantity: deleteTarget.quantity, price: deleteTarget.purchase_price, date: deleteTarget.purchase_date })}
            </p>
          </div>
        )}
        {deletePosition.isError && <p role="alert" className="text-sm text-destructive">{getApiErrorMessage(deletePosition.error, t("portfolio_delete_error"))}</p>}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={deletePosition.isPending}>{t("user_cancel")}</AlertDialogCancel>
          <Button
            variant="destructive"
            disabled={deletePosition.isPending}
            onClick={() => {
              if (!deleteTarget) return
              deletePosition.mutate(deleteTarget.id, { onSuccess: () => setDeleteTarget(null) })
            }}
          >
            {t(deletePosition.isPending ? "screener_deleting" : "screener_delete")}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
  return { askDelete, dialog }
}

/** Company name row with the delete button when the holding is a single purchase
 * (several purchases: each purchase row keeps its own delete). */
export function HoldingTitle({ company, onDelete }: { company: HeldCompany; onDelete: (p: PortfolioPosition) => void }) {
  const { t } = useTranslation()
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-3 text-lg font-bold">
        <TickerAvatar ticker={company.ticker} />
        <span className="truncate">{company.company_name}</span>
        <span className="font-mono-num text-sm font-medium text-muted-foreground">{company.ticker}</span>
      </div>
      {company.positions.length === 1 && (
        <Button variant="ghost" size="icon" aria-label={t("portfolio_delete_position_aria")} onClick={() => onDelete(company.positions[0])}>
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      )}
    </div>
  )
}
