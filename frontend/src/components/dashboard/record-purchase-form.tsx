import { useState, type FormEvent, type ReactNode } from "react"
import { Panel } from "@/components/ui/panel"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
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
  // Empty until the caller has picked a company (the portfolio dialog's picker).
  ticker: string
  reasons: ReasonOption[]
  // Inside a dialog: render just the form (the dialog supplies title/description).
  bare?: boolean
  // Content rendered at the top of the form, e.g. a company picker.
  header?: ReactNode
  onSuccess?: () => void
}

export function RecordPurchaseForm({ ticker, reasons, bare = false, header, onSuccess }: RecordPurchaseFormProps) {
  const { t, tReason } = useTranslation()
  const createPosition = useCreatePosition()
  const [quantity, setQuantity] = useState("")
  const [purchasePrice, setPurchasePrice] = useState("")
  const [purchaseDate, setPurchaseDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [reasonKeys, setReasonKeys] = useState<string[]>([])
  const [thesis, setThesis] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(false)
    if (!ticker) {
      setError(t("record_purchase_err_ticker"))
      return
    }
    if (reasonKeys.length === 0) {
      setError(t("record_purchase_err_reason"))
      return
    }
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
        reason_keys: reasonKeys,
        thesis: thesis.trim() || undefined,
      })
      setQuantity("")
      setPurchasePrice("")
      setReasonKeys([])
      setThesis("")
      setSuccess(true)
      onSuccess?.()
    } catch (err) {
      setError(getApiErrorMessage(err, t("record_purchase_err_default")))
    }
  }

  const form = (
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          {header}
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

          {/* Several reasons can back one purchase; each is frozen and tracked on its own. */}
          <fieldset className="flex flex-col gap-1.5" disabled={!ticker}>
            <legend className="mb-1.5 flex w-full items-center justify-between text-sm font-medium">
              <span>
                {t("record_purchase_field_reason")}
                <span aria-hidden="true" className="ml-0.5 text-destructive">*</span>
              </span>
              {reasonKeys.length > 0 && (
                <span className="text-xs font-normal text-[var(--text-muted)]">
                  {t("record_purchase_reasons_selected", { count: reasonKeys.length })}
                </span>
              )}
            </legend>
            {!ticker || reasons.length === 0 ? (
              <p className="rounded border border-dashed border-[var(--border-primary)] px-3 py-2 text-xs text-[var(--text-muted)]">
                {t(ticker ? "record_purchase_no_reasons" : "record_purchase_pick_company_first")}
              </p>
            ) : (
              <div className="flex max-h-48 flex-col overflow-y-auto rounded border border-[var(--border-primary)] bg-[var(--bg-input)]">
                {reasons.map((r) => {
                  const checked = reasonKeys.includes(r.reason_key)
                  return (
                    <label
                      key={r.reason_key}
                      className="flex cursor-pointer items-start gap-2.5 border-b border-[var(--border-primary)]/60 px-3 py-2 text-sm last:border-0 hover:bg-[var(--bg-hover)]"
                    >
                      <input
                        type="checkbox"
                        className="mt-0.5 h-4 w-4 flex-none accent-primary"
                        checked={checked}
                        onChange={() =>
                          setReasonKeys((keys) => (checked ? keys.filter((k) => k !== r.reason_key) : [...keys, r.reason_key]))
                        }
                      />
                      <span className="text-[var(--text-primary)]">{tReason(r.reason_key, r.description)}</span>
                    </label>
                  )
                })}
              </div>
            )}
          </fieldset>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="purchase-thesis">{t("record_purchase_field_thesis")}</Label>
            <Textarea
              id="purchase-thesis"
              rows={3}
              placeholder={t("record_purchase_thesis_placeholder")}
              value={thesis}
              onChange={(e) => setThesis(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">{t("record_purchase_thesis_hint")}</p>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
          {success && <p className="text-sm text-status-supported">{t("record_purchase_success")}</p>}

          <Button type="submit" disabled={createPosition.isPending}>
            {createPosition.isPending ? t("record_purchase_submit_pending") : t("record_purchase_submit")}
          </Button>
        </form>
  )

  if (bare) return form
  return (
    <Panel title={t("record_purchase_title")} description={t("record_purchase_description")} color="var(--accent-green)">
      {form}
    </Panel>
  )
}
