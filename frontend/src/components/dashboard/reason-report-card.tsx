import { Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/status-badge"
import type { Reason, ReportReason } from "@/types"
import { useTranslation } from "@/i18n/context"

interface ReasonReportCardProps {
  reportReason: ReportReason
  reasonMeta?: Reason
  onDelete?: () => void
  deletable?: boolean
}

export function ReasonReportCard({ reportReason, reasonMeta, onDelete, deletable }: ReasonReportCardProps) {
  const { t, tReason } = useTranslation()
  const statusLabel = (status: string) => t("status_" + status.toLowerCase().replace(/ /g, "_"))

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-card)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold leading-snug">
            {tReason(reportReason.reason_key, reportReason.description)}
          </p>
          {reasonMeta && (
            <p className="mt-1 font-mono-num text-xs text-muted-foreground">
              {reasonMeta.metric} {reasonMeta.comparison} {reasonMeta.threshold}
              {reasonMeta.denominator_metric ? ` / ${reasonMeta.denominator_metric}` : ""}
            </p>
          )}
        </div>
        <StatusBadge status={reportReason.status} />
      </div>
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-0.5">
          <span className="font-mono-num text-lg font-bold">
            {reportReason.computed_value ?? "—"}
          </span>
          <span className="text-xs text-muted-foreground">
            {reportReason.as_of ? t("reason_card_as_of", { date: reportReason.as_of }) : t("reason_card_no_value")}
            {reportReason.previous_status && reportReason.previous_status !== reportReason.status
              ? ` · ${t("reason_card_was", { status: statusLabel(reportReason.previous_status) })}`
              : ""}
          </span>
        </div>
        {deletable && onDelete && (
          <Button variant="ghost" size="icon" onClick={onDelete} aria-label={t("reason_card_delete_aria")}>
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        )}
      </div>
    </div>
  )
}
