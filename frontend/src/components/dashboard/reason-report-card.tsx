import { AlertTriangle, Sparkles, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/status-badge"
import { ReasonTrendChart, formatRatio, formatRule } from "@/components/dashboard/reason-trend-chart"
import type { InvestigationReasonResult, Reason, ReportReason } from "@/types"
import { useTranslation } from "@/i18n/context"

interface ReasonReportCardProps {
  reportReason: ReportReason
  reasonMeta?: Reason
  onDelete?: () => void
  deletable?: boolean
  // The stored AI Summary's verdict for this reason, if one was ever generated.
  ai?: InvestigationReasonResult
}

export function AiNote({ ai }: { ai: InvestigationReasonResult }) {
  const { t } = useTranslation()
  return (
    <div className="rounded-md border border-primary/20 bg-primary/5 p-2.5">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary">
          <Sparkles className="h-3 w-3" />
          {t("ai_note_label")}
        </span>
        <StatusBadge status={ai.status} />
      </div>
      <p className="text-xs leading-relaxed text-[var(--text-secondary)]">{ai.rationale}</p>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[var(--text-muted)]">
        <span>{t("investigate_confidence", { confidence: t(`confidence_${ai.confidence}`) })}</span>
        {ai.human_review_recommended && (
          <span className="inline-flex items-center gap-1 text-status-weakened">
            <AlertTriangle className="h-3 w-3" />
            {t("investigate_review_recommended")}
          </span>
        )}
      </div>
    </div>
  )
}

export function ReasonReportCard({ reportReason, reasonMeta, onDelete, deletable, ai }: ReasonReportCardProps) {
  const { t, tReason } = useTranslation()

  const history = reportReason.history ?? []
  const hasChart = history.length > 0 && reportReason.threshold != null && reportReason.comparison != null

  // "scope — condition" (same wording as the screener's rule list), status,
  // then the trend against the threshold instead of a bare number.
  return (
    <div className="flex flex-col gap-2 rounded-md border border-[var(--border-primary)] p-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <span className="min-w-0">
          <span className="font-mono-num text-xs text-muted-foreground">{reasonMeta?.ticker ?? t("screener_ticker_any")}</span>{" "}
          — {tReason(reportReason.reason_key, reportReason.description)}
        </span>
        <div className="flex flex-none items-center gap-1">
          <StatusBadge status={reportReason.status} />
          {deletable && onDelete && (
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onDelete} aria-label={t("reason_card_delete_aria")}>
              <Trash2 className="h-3.5 w-3.5 text-destructive" />
            </Button>
          )}
        </div>
      </div>
      {hasChart && (
        <div className="flex items-end gap-4">
          <div className="min-w-0 flex-1">
            <ReasonTrendChart points={history} threshold={reportReason.threshold!} />
          </div>
          <div className="flex-none text-right">
            <div className="text-[10px] text-[var(--text-muted)]">{t("reason_chart_latest", { date: history[history.length - 1].as_of })}</div>
            <div className="font-mono-num text-base font-bold text-[var(--text-primary)]">{formatRatio(history[history.length - 1].value)}</div>
            <div className="mt-0.5 flex items-center justify-end gap-1 text-[10px] text-[var(--text-muted)]">
              <span className="inline-block w-3 border-t border-dashed border-[var(--text-muted)]" aria-hidden="true" />
              {t("reason_chart_threshold", { rule: formatRule(reportReason.comparison!, reportReason.threshold!) })}
            </div>
          </div>
        </div>
      )}
      {ai && <AiNote ai={ai} />}
    </div>
  )
}
