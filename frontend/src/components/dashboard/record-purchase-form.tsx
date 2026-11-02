import { useEffect, useState, type FormEvent, type ReactNode } from "react"
import { Check, ChevronRight, ArrowLeft } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { useReasons } from "@/hooks/use-reasons"
import { useCreatePosition } from "@/hooks/use-positions"
import { useHistory, useQuote } from "@/hooks/use-market"
import type { HistoryRange } from "@/types"
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
  rule_definition?: {preview?: string; evaluation_period: string} | null
}

// Suggested purchase price for the picked company and date: the latest quote
// when the date is today (or later than the newest close), otherwise the
// close on or before that date. Older dates only have weekly/monthly closes
// available, so `granularity` says which one was used. Display-only market
// data -- the user can always overwrite it.
function useSuggestedPrice(ticker: string, purchaseDate: string) {
  const ageDays = purchaseDate ? (Date.now() - new Date(purchaseDate).getTime()) / 86_400_000 : 0
  const range: HistoryRange = ageDays <= 25 ? "1mo" : ageDays <= 175 ? "6mo" : ageDays <= 5 * 365 ? "5y" : "max"
  const granularity = range === "5y" ? "week" : range === "max" ? "month" : "day"
  const { data: quote, isError: quoteFailed } = useQuote(ticker)
  const { data: history, isFetching, isError: historyFailed } = useHistory(ticker, range)
  if (!ticker || !purchaseDate) return { loading: false, unavailable: false, suggestion: null }
  const lastClose = history?.length ? history[history.length - 1] : null
  if ((!lastClose || purchaseDate > lastClose.date) && quote?.price) {
    return { loading: false, unavailable: false, suggestion: { price: quote.price, source: "latest" as const, date: null, granularity } }
  }
  const point = [...(history ?? [])].reverse().find((p) => p.date <= purchaseDate)
  if (point) return { loading: false, unavailable: false, suggestion: { price: point.close, source: "close" as const, date: point.date, granularity } }
  // Price provider down or out of quota (or no close that far back): say so
  // rather than leaving the field silently empty.
  return { loading: isFetching, unavailable: !isFetching && (historyFailed || quoteFailed || Boolean(history)), suggestion: null }
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

export function RecordPurchaseForm({ ticker, reasons: reportReasons, bare = false, header, onSuccess }: RecordPurchaseFormProps) {
  const { t, tReason, lang } = useTranslation()
  const { data: defaults } = useReasons()
  const reasons = defaults ?? reportReasons
  const th=lang==='th'
  const [step,setStep]=useState(1)
  const createPosition = useCreatePosition()
  const [quantity, setQuantity] = useState("")
  const [purchasePrice, setPurchasePrice] = useState("")
  const [purchaseDate, setPurchaseDate] = useState(() => new Date().toISOString().slice(0, 10))
  // Once the user types a price, stop overwriting it with the suggestion.
  const [priceEdited, setPriceEdited] = useState(false)
  const { loading: priceLoading, unavailable: priceUnavailable, suggestion } = useSuggestedPrice(ticker, purchaseDate)
  const suggestedPrice = suggestion ? suggestion.price.toFixed(2) : null

  useEffect(() => {
    if (!priceEdited && suggestedPrice) setPurchasePrice(suggestedPrice)
  }, [suggestedPrice, priceEdited])
  const [reasonKeys, setReasonKeys] = useState<string[]>(["revenue_growth", "operating_margin", "debt_growth"])
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if(step!==3) return
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
      })
      setQuantity("")
      setPurchasePrice("")
      setPriceEdited(false)
      setReasonKeys(["revenue_growth", "operating_margin", "debt_growth"])
      setStep(1)
      setSuccess(true)
      onSuccess?.()
    } catch (err) {
      setError(getApiErrorMessage(err, t("record_purchase_err_default")))
    }
  }

  function nextStep(){
    if(step===1&&(!ticker||!Number.isFinite(Number(quantity))||Number(quantity)<=0||!Number.isFinite(Number(purchasePrice))||Number(purchasePrice)<=0||!purchaseDate)){setError(th?'กรุณาระบุบริษัท จำนวนหุ้น ราคา และวันที่ให้ครบ':'Enter a company, positive quantity and price, and a purchase date.');return}
    if(step===2&&!reasonKeys.length){setError(t('record_purchase_err_reason'));return}
    setError(null);setStep(s=>Math.min(3,s+1))
  }
  const form = (<>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <ol className="mb-2 grid grid-cols-3 gap-2" aria-label={th?'ขั้นตอนบันทึกการซื้อ':'Purchase steps'}>{[th?'ข้อมูลการซื้อ':'Purchase',th?'เหตุผลการลงทุน':'Reasons',th?'ยืนยันข้อมูล':'Confirm'].map((label,i)=><li key={label} aria-current={step===i+1?'step':undefined} className="flex items-center gap-2 text-xs"><span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full ${step>=i+1?'bg-primary text-white':'bg-muted text-muted-foreground'}`}>{step>i+1?<Check size={14}/>:i+1}</span><span className={step===i+1?'font-semibold':'text-muted-foreground'}>{label}</span></li>)}</ol>
          <div className={step===1?'space-y-4':'hidden'}>
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
                onChange={(e) => { setPurchasePrice(e.target.value); setPriceEdited(true) }}
              />
              {priceLoading && <p className="text-[11px] text-[var(--text-muted)]">{t("purchase_price_loading")}</p>}
              {priceUnavailable && <p className="text-[11px] text-status-weakened">{t("purchase_price_unavailable")}</p>}
              {suggestion && (
                <p className="text-[11px] text-[var(--text-muted)]">
                  {suggestion.source === "latest"
                    ? t("purchase_price_latest")
                    : t(`purchase_price_close_${suggestion.granularity}`, { date: suggestion.date ?? "" })}
                  {priceEdited && purchasePrice !== suggestedPrice && (
                    <>
                      {" · "}
                      <button
                        type="button"
                        className="text-primary hover:underline"
                        onClick={() => { setPurchasePrice(suggestedPrice ?? ""); setPriceEdited(false) }}
                      >
                        {t("purchase_price_use", { price: suggestedPrice ?? "" })}
                      </button>
                    </>
                  )}
                </p>
              )}
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

          </div>
          <div className={step===2?'space-y-4':'hidden'}>
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
                {reasons.filter(r => ["revenue_growth", "operating_margin", "debt_growth"].includes(r.reason_key)).map((r) => {
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
                      <span className="text-[var(--text-primary)]">{tReason(r.reason_key, r.description)}{r.rule_definition && <small className="mt-1 block text-muted-foreground">{r.rule_definition.preview} · {r.rule_definition.evaluation_period}</small>}</span>
                    </label>
                  )
                })}
              </div>
            )}
          </fieldset>

          </div>
          {step===3&&<div className="rounded-xl border bg-primary/5 p-5 space-y-4"><h3 className="text-lg">{th?'ตรวจสอบก่อนบันทึก':'Review your purchase'}</h3><div className="grid grid-cols-2 gap-4 text-sm"><p>{ticker}<small className="block text-muted-foreground">{purchaseDate}</small></p><p>{quantity} × ${purchasePrice}<strong className="mt-1 block text-primary">${(Number(quantity)*Number(purchasePrice)).toLocaleString(undefined,{maximumFractionDigits:2})}</strong></p></div><div className="space-y-2">{reasonKeys.map(key=><p key={key} className="flex gap-2 text-sm"><Check className="h-4 w-4 shrink-0 text-primary"/>{tReason(key,reasons.find(r=>r.reason_key===key)?.description||key)}</p>)}</div><p className="text-xs text-muted-foreground">{th?'เหตุผลเวอร์ชันนี้จะถูกเก็บพร้อมรายการซื้อ เพื่อใช้ทบทวนในภายหลัง':'This purchase preserves the current version of each reason for future review.'}</p></div>}
          {error && <p className="text-sm text-destructive">{error}</p>}
          {success && <p className="text-sm text-status-supported">{t("record_purchase_success")}</p>}

          <div className="flex justify-between gap-3 border-t pt-4">{step>1?<Button type="button" variant="outline" onClick={()=>{setStep(s=>s-1);setError(null)}}><ArrowLeft size={16}/>{th?'ย้อนกลับ':'Back'}</Button>:<span/>}
          {step<3?<Button key="next" type="button" onClick={e=>{e.preventDefault();nextStep()}}>{th?'ถัดไป':'Continue'}<ChevronRight size={16}/></Button>:<Button key="save" type="submit" disabled={createPosition.isPending}>{createPosition.isPending?t('record_purchase_submit_pending'):t('record_purchase_submit')}</Button>}</div>
        </form>
      </>)

  if (bare) return form
  return (
    <Panel title={t("record_purchase_title")} description={t("record_purchase_description")} color="var(--accent-green)">
      {form}
    </Panel>
  )
}
