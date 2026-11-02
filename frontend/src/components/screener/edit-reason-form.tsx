import { useState, type FormEvent } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { apiClient, getApiErrorMessage } from "@/api/client"
import { useTranslation } from "@/i18n/context"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { FinancialFormulaInfo } from "./financial-data-info"
import type { Reason, ComparisonOp } from "@/types"

export function EditReasonForm({ reason, onSaved }: { reason: Reason; onSaved: (key: string) => void }) {
  const { t, tReason } = useTranslation()
  const client = useQueryClient()
  const [description, setDescription] = useState(tReason(reason.reason_key, reason.description))
  const [comparison, setComparison] = useState<ComparisonOp>(reason.comparison)
  const [threshold, setThreshold] = useState(String(Number((reason.threshold * 100).toPrecision(15))))
  const mutation = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.patch<{reason_key: string}>(`/reasons/${encodeURIComponent(reason.reason_key)}`, { description: description.trim(), comparison, threshold: Number(threshold) / 100 })
      return data
    },
    onSuccess: async (data) => {
      await Promise.all(["reasons", "screen", "report", "portfolio"].map(key => client.invalidateQueries({queryKey: [key]})))
      onSaved(data.reason_key)
    },
  })
  function submit(e: FormEvent) {
    e.preventDefault()
    if (description.trim() && threshold.trim() && Number.isFinite(Number(threshold))) mutation.mutate()
  }
  return <form onSubmit={submit} className="flex flex-col gap-4">
    <p className="text-sm text-muted-foreground">{t("edit_reason_scope")}</p>
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="edit-reason-description">{t("create_reason_field_description")}</Label>
      <Input id="edit-reason-description" value={description} onChange={e => setDescription(e.target.value)} required maxLength={1000} />
    </div>
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="edit-reason-comparison">{t("create_reason_field_comparison")}</Label>
      <Select id="edit-reason-comparison" value={comparison} onChange={v => setComparison(v as ComparisonOp)} options={([">", ">=", "<", "<="] as const).map(value => ({value,label:value}))} />
    </div>
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="edit-reason-threshold">{t("create_reason_field_threshold")}</Label>
      <div className="relative">
<Input className="pr-9" id="edit-reason-threshold" type="number" step="any" required value={threshold} onChange={e => setThreshold(e.target.value)} />
<span aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-muted-foreground">%</span>
</div>
    </div>
    <FinancialFormulaInfo kind={reason.kind} metric={reason.metric} denominator={reason.denominator_metric ?? ""} comparison={comparison} threshold={threshold} />
    {mutation.isError && <p role="alert" className="text-sm text-destructive">{getApiErrorMessage(mutation.error,t("create_reason_err_default"))}</p>}
    <Button type="submit" disabled={mutation.isPending || !description.trim() || !threshold.trim()}>{t(mutation.isPending ? "create_reason_submit_pending" : "edit_reason_save")}</Button>
  </form>
}
