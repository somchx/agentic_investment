import { useState } from "react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { RecordPurchaseForm } from "@/components/dashboard/record-purchase-form"
import { useCompanies } from "@/hooks/use-companies"
import { useReport } from "@/hooks/use-report"
import { useTranslation } from "@/i18n/context"

/** "Record a purchase" from the holdings table: same form as the dashboard
 * modal, plus a company picker since the table isn't scoped to one ticker.
 * The reason list follows the picked company. */
export function RecordPurchaseDialog({ open, onOpenChange, onRecorded }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onRecorded?: (ticker: string) => void
}) {
  const { t } = useTranslation()
  const { data: companies } = useCompanies()
  const [ticker, setTicker] = useState("")
  const { data: report } = useReport(ticker)

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) setTicker(""); onOpenChange(next) }}>
      <DialogContent className="flex max-h-[85vh] max-w-lg flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="shrink-0 border-b border-[var(--border-primary)] px-6 py-4 pr-12">
          <DialogTitle>{t("record_purchase_title")}</DialogTitle>
          <DialogDescription>{t("record_purchase_description")}</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-y-auto p-6">
          <RecordPurchaseForm
            // Remount per company so a reason picked for one ticker can't carry over to another.
            key={ticker || "none"}
            bare
            ticker={ticker}
            reasons={report?.reasons ?? []}
            header={
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="purchase-company">{t("record_purchase_field_company")}</Label>
                <Select
                  id="purchase-company"
                  value={ticker}
                  onChange={setTicker}
                  searchable
                  placeholder={t("record_purchase_company_placeholder")}
                  searchPlaceholder={t("company_search_placeholder")}
                  className="flex w-full items-center justify-between gap-2 rounded border border-[var(--border-primary)] bg-[var(--bg-input)] px-3 py-1.5 text-sm text-[var(--text-primary)]"
                  options={(companies ?? []).map((c) => ({ value: c.ticker, label: `${c.ticker} — ${c.name}` }))}
                />
              </div>
            }
            onSuccess={() => {
              const recorded = ticker
              setTicker("")
              onOpenChange(false)
              onRecorded?.(recorded)
            }}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}
