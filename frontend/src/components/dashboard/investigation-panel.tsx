import { useState } from "react"
import { CalendarDays, Clock, Database, RefreshCw, ShieldAlert, Sparkles } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { StatusBadge } from "@/components/status-badge"
import { CostConfirmDialog } from "@/components/cost-confirm-dialog"
import { useInvestigate, useLatestInvestigation } from "@/hooks/use-report"
import { getApiErrorMessage } from "@/api/client"
import { useTranslation } from "@/i18n/context"
import { Button } from "@/components/ui/button"
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import { AiNote, ReasonReportCard } from "@/components/dashboard/reason-report-card"
import type { CompanyReport, Reason, ReportReason } from "@/types"

// The Structured Investigation path (POST /api/investigate/{ticker}) --
// runs agent.run_with_llm directly, gated by the Evidence Assessor, and
// shows the full tool-call trace + per-reason confidence/rationale. This
// is deliberately separate from the free-form "Ask the agent" chat page:
// that one has no schema and no Evidence Gate at all. See Code Audit
// Session 3, item 5.
//
// Shown to users as "AI Summary": a sample preview until they run it, an
// animated thinking state while the LLM works, then the result. The latest
// result is stored server-side per user + ticker and reloaded for free when
// the modal reopens; regenerating replaces it.

function ThinkingState({ ticker }: { ticker: string }) {
  const { t } = useTranslation()
  return (
    <div role="status" aria-live="polite" className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-primary/30 bg-primary/5 px-4 py-8 text-center">
      <div className="relative grid h-12 w-12 place-items-center">
        <span className="absolute inset-0 animate-ping rounded-full bg-primary/20" />
        <span className="relative grid h-12 w-12 place-items-center rounded-full brand-gradient text-white shadow-glow">
          <Sparkles className="h-5 w-5 animate-pulse" />
        </span>
      </div>
      <p className="flex items-center gap-1 text-sm font-semibold text-[var(--text-primary)]">
        {t("ai_summary_thinking", { ticker })}
        <span className="inline-flex gap-0.5" aria-hidden="true">
          {[0, 150, 300].map((delay) => (
            <span key={delay} className="h-1 w-1 animate-bounce rounded-full bg-primary" style={{ animationDelay: `${delay}ms` }} />
          ))}
        </span>
      </p>
      <p className="text-xs text-[var(--text-muted)]">{t("ai_summary_thinking_hint")}</p>
      <div className="mt-2 grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
        {[0, 1].map((i) => (
          <div key={i} className="space-y-2 rounded-md border border-[var(--border-primary)] bg-[var(--bg-card)] p-3 text-left">
            <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
            <div className="h-2.5 w-full animate-pulse rounded bg-muted" />
            <div className="h-2.5 w-4/5 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>
    </div>
  )
}

// Static, clearly-labelled example so users know what a run produces before paying for one.
function SamplePreview() {
  const { t } = useTranslation()
  return (
    <div className="relative rounded-lg border border-dashed border-[var(--border-primary)] p-3">
      <span className="absolute -top-2.5 left-3 rounded-full bg-[var(--bg-card)] px-2 text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
        {t("ai_summary_sample_label")}
      </span>
      <div className="pointer-events-none select-none opacity-70" aria-hidden="true">
        <div className="mb-1.5 flex items-center justify-between gap-2">
          <span className="text-sm font-semibold">{t("ai_summary_sample_reason")}</span>
          <StatusBadge status="Supported" />
        </div>
        <p className="text-xs text-[var(--text-muted)]">{t("ai_summary_sample_rationale")}</p>
        <div className="mt-2 text-[11px] text-[var(--text-ghost)]">{t("investigate_confidence", { confidence: t("confidence_high") })}</div>
      </div>
    </div>
  )
}

export function InvestigationPanel({ ticker, reasons, dataFreshness, reasonsMeta, onDeleteReason, reasonsAnchorId = "reason-checks" }: {
  ticker: string
  // Scroll target for the reason list; unique per company when several panels share a page.
  reasonsAnchorId?: string
  reasons: ReportReason[]
  dataFreshness?: CompanyReport["data_freshness"]
  reasonsMeta?: Reason[]
  onDeleteReason: (reasonKey: string) => void
}) {
  const { t, tReason } = useTranslation()
  const investigate = useInvestigate(ticker)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const { data: report, isLoading: loadingSaved } = useLatestInvestigation(ticker)
  const [error, setError] = useState<string | null>(null)
  const [deleteReason, setDeleteReason] = useState<ReportReason | null>(null)

  // Hide the old summary while a new one is being generated.
  const showAi = report && !investigate.isPending ? report : null
  const aiReasons = showAi && !showAi.escalated ? showAi.reasons : []
  const aiByKey = new Map(aiReasons.map((r) => [r.reason_key, r]))
  const unmatchedAi = aiReasons.filter((r) => !reasons.some((rr) => rr.reason_key === r.reason_key))

  async function run() {
    setError(null)
    try {
      await investigate.mutateAsync()
    } catch (err) {
      setError(getApiErrorMessage(err, t("investigate_err_default")))
    }
  }

  return (
    <Panel
      title={<span className="inline-flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5 text-primary" />{t("ai_summary_title")}</span>}
      description={t("ai_summary_description", { ticker })}
      color="var(--brand)"
      action={
        // Once a summary exists, "generate again" sits beside the heading instead of above the result.
        report && !investigate.isPending ? (
          <button
            type="button"
            onClick={() => setConfirmOpen(true)}
            className="inline-flex flex-none items-center gap-1.5 rounded-full brand-gradient px-3 py-1.5 text-xs font-semibold text-white shadow-glow transition-opacity hover:opacity-90"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            {t("ai_summary_regenerate")}
          </button>
        ) : undefined
      }
    >
      <div className="flex flex-col gap-4">
        {investigate.isPending && <ThinkingState ticker={ticker} />}
        {error && <p className="text-sm text-destructive">{error}</p>}

        {showAi && (showAi.data_as_of || showAi.generated_at) && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-[var(--text-muted)]">
            {showAi.data_as_of && (
              <span className="inline-flex items-center gap-1"><CalendarDays className="h-3 w-3" />{t("ai_summary_data_as_of", { date: showAi.data_as_of })}</span>
            )}
            {showAi.generated_at && (
              <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" />{t("ai_summary_generated_at", { date: new Date(showAi.generated_at).toLocaleString() })}</span>
            )}
          </div>
        )}

        {showAi?.escalated && (
          <div className="flex items-start gap-2 rounded-md border border-status-broken/40 bg-status-broken/10 p-3 text-sm text-status-broken">
            <ShieldAlert className="mt-0.5 h-4 w-4 flex-none" />
            <div>
              <p className="font-semibold">{t("investigate_escalated_title")}</p>
              <p className="mt-1 text-xs">{showAi.escalation_reason}</p>
            </div>
          </div>
        )}

        {/* The charts read cached SEC filings, not live data -- say how old that cache is. */}
        {reasons.length > 0 && (
          <p className={`flex items-center gap-1 text-[11px] ${dataFreshness?.is_stale ? "text-status-weakened" : "text-[var(--text-muted)]"}`}>
            <Database className="h-3 w-3" />
            {dataFreshness?.cached_at
              ? t(dataFreshness.is_stale ? "sec_fetched_stale" : "sec_fetched_at", { when: new Date(dataFreshness.cached_at).toLocaleString() })
              : t("sec_fetched_unknown")}
          </p>
        )}

        {/* Mechanical check per reason (chart), with the AI's note underneath when a summary exists. */}
        <div id={reasonsAnchorId} className="flex scroll-mt-4 flex-col gap-2">
          {reasons.map((rr) => {
            const meta = reasonsMeta?.find((r) => r.reason_key === rr.reason_key)
            return (
              <ReasonReportCard
                key={rr.reason_key}
                reportReason={rr}
                reasonMeta={meta}
                deletable={meta ? !meta.is_builtin : false}
                onDelete={() => setDeleteReason(rr)}
                ai={aiByKey.get(rr.reason_key)}
              />
            )
          })}
          {/* AI verdicts for reasons no longer in the list (e.g. deleted since) still get shown. */}
          {unmatchedAi.map((r) => (
            <div key={r.reason_key} className="flex flex-col gap-2 rounded-md border border-[var(--border-primary)] p-3 text-sm">
              <span>{tReason(r.reason_key, r.reason_key)}</span>
              <AiNote ai={r} />
            </div>
          ))}
        </div>

        {loadingSaved && <p className="text-xs text-[var(--text-muted)]">{t("ai_summary_loading")}</p>}

        {!loadingSaved && !report && !investigate.isPending && (
          <>
            <SamplePreview />
            <button
              type="button"
              onClick={() => setConfirmOpen(true)}
              className="inline-flex w-fit items-center gap-1.5 self-center rounded-full brand-gradient px-4 py-2 text-sm font-semibold text-white shadow-glow transition-opacity hover:opacity-90"
            >
              <Sparkles className="h-4 w-4" />
              {t("ai_summary_generate")}
            </button>
          </>
        )}

        {showAi && (
          <details className="rounded-md border border-[var(--border-primary)] p-3 text-xs">
            <summary className="cursor-pointer font-semibold text-[var(--text-secondary)]">
              {t("investigate_trace_title")}
            </summary>
            <ul className="mt-2 flex flex-col gap-1 font-mono-num text-[var(--text-muted)]">
              {showAi.trace.map((line, i) => (
                <li key={i} className="break-all">
                  {line}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>

      <AlertDialog open={!!deleteReason} onOpenChange={(open) => { if (!open) setDeleteReason(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("screener_delete_title")}</AlertDialogTitle>
            <AlertDialogDescription>{t("screener_delete_description")}</AlertDialogDescription>
          </AlertDialogHeader>
          <p className="text-sm font-medium">{deleteReason && tReason(deleteReason.reason_key, deleteReason.description)}</p>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("user_cancel")}</AlertDialogCancel>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleteReason) onDeleteReason(deleteReason.reason_key)
                setDeleteReason(null)
              }}
            >
              {t("screener_delete")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <CostConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("investigate_dialog_title")}
        description={t("investigate_dialog_description", { ticker })}
        onConfirm={() => {
          setConfirmOpen(false)
          void run()
        }}
        isPending={investigate.isPending}
      />
    </Panel>
  )
}
