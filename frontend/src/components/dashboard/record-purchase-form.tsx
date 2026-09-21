import { useState, type FormEvent } from "react"
import { Panel } from "@/components/ui/panel"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { useCreatePosition } from "@/hooks/use-positions"
import { getApiErrorMessage } from "@/api/client"
import { useTranslation } from "@/i18n/context"

// Deliberately narrower than the full `Reason` shape: the picker needs to
// offer every reason evaluated for this ticker (built-in + custom, as
// returned by the evidence report), not just this user's custom ones --
// GET /api/reasons?ticker= only returns the latter, which would silently
// make built-in reasons unselectable here.
interface ReasonOption {
  reason_key: string
  description: string
}

interface RecordPurchaseFormProps {
  ticker: string
  reasons: ReasonOption[]
}

export function RecordPurchaseForm({ ticker, reasons }: RecordPurchaseFormProps) {
  const { t, tReason } = useTranslation()
  const createPosition = useCreatePosition()
  const [quantity, setQuantity] = useState("")
  const [purchasePrice, setPurchasePrice] = useState("")
  const [purchaseDate, setPurchaseDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [reasonKey, setReasonKey] = useState<string>("")
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(false)
    const qty = Number(quantity)
    const price = Number(purchasePrice)
    if (!qty || qty <= 0) {
      setError(t("record_purchase_err_quantity"))
      return
    }
    if (!price || price <= 0) {
      setError(t("record_purchase_err_price"))
      return
    }
    try {
      await createPosition.mutateAsync({
        ticker,
        quantity: qty,
        purchase_price: price,
        purchase_date: purchaseDate,
        reason_key: reasonKey || undefined,
      })
      setQuantity("")
      setPurchasePrice("")
      setReasonKey("")
      setSuccess(true)
    } catch (err) {
      setError(getApiErrorMessage(err, t("record_purchase_err_default")))
    }
  }

  return (
    <Panel title={t("record_purchase_title")} description={t("record_purchase_description")} color="var(--accent-green)">
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="purchase-quantity">{t("record_purchase_field_quantity")}</Label>
              <Input
                id="purchase-quantity"
                type="number"
                step="any"
                min="0"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="purchase-price">{t("record_purchase_field_price")}</Label>
              <Input
                id="purchase-price"
                type="number"
                step="any"
                min="0"
                value={purchasePrice}
                onChange={(e) => setPurchasePrice(e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="purchase-date">{t("record_purchase_field_date")}</Label>
            <Input
              id="purchase-date"
              type="date"
              value={purchaseDate}
              onChange={(e) => setPurchaseDate(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="purchase-reason">{t("record_purchase_field_reason")}</Label>
            <Select
              id="purchase-reason"
              value={reasonKey}
              onChange={setReasonKey}
              placeholder={t("record_purchase_reason_placeholder")}
              className="flex w-full items-center justify-between gap-2 rounded border border-[var(--border-primary)] bg-[var(--bg-input)] px-3 py-1.5 text-sm text-[var(--text-primary)] disabled:opacity-60"
              options={reasons.map((r) => ({ value: r.reason_key, label: tReason(r.reason_key, r.description) }))}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
          {success && <p className="text-sm text-status-supported">{t("record_purchase_success")}</p>}

          <Button type="submit" disabled={createPosition.isPending}>
            {createPosition.isPending ? t("record_purchase_submit_pending") : t("record_purchase_submit")}
          </Button>
        </form>
    </Panel>
  )
}
