import { useState, type ReactNode } from "react"
import { AlertTriangle, ShieldAlert, Swords, Users } from "lucide-react"
import { Button } from "@/components/ui/button"
import { CostConfirmDialog } from "@/components/cost-confirm-dialog"
import { useAttackThesis, useDebateThesis, useThesisDebates, useThesisReviews } from "@/hooks/use-positions"
import { getApiErrorMessage } from "@/api/client"
import { useTranslation } from "@/i18n/context"
import { cn } from "@/lib/utils"
import type { DebateCase, PositionReason, ThesisDebate, ThesisReview } from "@/types"
import { Select } from "@/components/ui/select"

const VERDICT_KEY: Record<string, string> = {
  "Still Holds": "thesis_verdict_still_holds",
  Weakened: "thesis_verdict_weakened",
  Broken: "thesis_verdict_broken",
}

const VERDICT_STYLE: Record<string, string> = {
  "Still Holds": "border-status-supported/40 bg-status-supported/10 text-status-supported",
  Weakened: "border-status-weakened/40 bg-status-weakened/10 text-status-weakened",
  Broken: "border-status-broken/40 bg-status-broken/10 text-status-broken",
}

function DebateSideCard({
  title,
  colorClass,
  side,
  rebuttal,
}: {
  title: string
  colorClass: string
  side: DebateCase | null
  rebuttal: string | null
}) {
  const { t } = useTranslation()
  if (!side || side.escalated) {
    return (
      <div className="flex-1 rounded-md border border-dashed border-[var(--border-primary)] p-2.5">
        <div className={cn("text-xs font-semibold", colorClass)}>{title}</div>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          {side?.escalation_reason || t("thesis_debate_side_escalated")}
        </p>
      </div>
    )
  }
  return (
    <div className="flex-1 rounded-md border border-[var(--border-primary)] p-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className={cn("text-xs font-semibold", colorClass)}>{title}</span>
        <span className="text-[10px] text-[var(--text-ghost)]">
          {t("investigate_confidence", { confidence: t(`confidence_${side.confidence}`) })}
        </span>
      </div>
      <ul className="mt-1.5 flex flex-col gap-1 text-xs text-[var(--text-primary)]">
        {side.key_points?.map((p, i) => (
          <li key={i} className="list-disc pl-3.5 marker:text-[var(--text-ghost)]">
            {p}
          </li>
        ))}
      </ul>
      <details className="mt-1.5">
        <summary className="cursor-pointer text-[11px] font-semibold text-[var(--text-muted)]">
          {t("thesis_strongest_evidence_label")}
        </summary>
        <p className="mt-1 text-xs text-[var(--text-muted)]">{side.strongest_evidence}</p>
      </details>
      {rebuttal && (
        <div className="mt-2 border-t border-[var(--border-primary)] pt-1.5">
          <div className="text-[11px] font-semibold text-[var(--text-ghost)]">{t("thesis_rebuttal_title")}</div>
          <p className="mt-0.5 text-xs text-[var(--text-muted)]">{rebuttal}</p>
        </div>
      )}
    </div>
  )
}

function RunHistory<T>({ items, render }: { items: T[]; render: (item: T) => ReactNode }) {
  const { t } = useTranslation()
  const [latest, ...older] = items
  return (
    <div className="flex flex-col gap-2">
      {render(latest)}
      {older.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-[11px] font-semibold text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            {t("thesis_show_older", { count: older.length })}
          </summary>
          <div className="mt-2 flex flex-col gap-2 opacity-80">{older.map(render)}</div>
        </details>
      )}
    </div>
  )
}

// Which reason a run challenged -- shown once a purchase has more than one.
function RunReasonLabel({ reasonKey, reasons }: { reasonKey: string; reasons: PositionReason[] }) {
  const { t, tReason } = useTranslation()
  if (reasons.length < 2) return null
  const reason = reasons.find((r) => r.reason_key === reasonKey)
  return (
    <p className="mb-1.5 text-[11px] text-[var(--text-muted)]">
      {t("thesis_run_reason", { reason: tReason(reasonKey, reason?.reason_snapshot?.description ?? reasonKey) })}
    </p>
  )
}

function ReviewCard({ review: r, reasons }: { review: ThesisReview; reasons: PositionReason[] }) {
  const { t } = useTranslation()
  return (
    <div className="rounded-md border border-[var(--border-primary)] p-2.5">
      <RunReasonLabel reasonKey={r.reason_key} reasons={reasons} />
      {r.escalated ? (
        <div className="flex items-start gap-2 text-xs text-status-broken">
          <ShieldAlert className="mt-0.5 h-3.5 w-3.5 flex-none" />
          <div>
            <p className="font-semibold">{t("thesis_escalated_title")}</p>
            <p className="mt-0.5 text-[var(--text-muted)]">{r.escalation_reason}</p>
          </div>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between gap-2">
            <span
              className={cn(
                "inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                VERDICT_STYLE[r.thesis_status ?? ""] ?? "border-[var(--border-primary)] text-[var(--text-muted)]",
              )}
            >
              {VERDICT_KEY[r.thesis_status ?? ""] ? t(VERDICT_KEY[r.thesis_status ?? ""]) : r.thesis_status}
            </span>
            <span className="text-[10px] text-[var(--text-ghost)]">
              {new Date(r.created_at).toLocaleDateString()}
            </span>
          </div>
          <p className="mt-1.5 text-xs text-[var(--text-primary)]">{r.rationale}</p>
          <details className="mt-1.5">
            <summary className="cursor-pointer text-[11px] font-semibold text-[var(--text-muted)]">
              {t("thesis_counter_evidence_label")}
            </summary>
            <p className="mt-1 text-xs text-[var(--text-muted)]">{r.counter_evidence}</p>
          </details>
          {r.human_review_recommended && (
            <div className="mt-1.5 flex items-center gap-1 text-[11px] text-status-weakened">
              <AlertTriangle className="h-3 w-3" />
              {t("investigate_review_recommended")}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function DebateCard({ debate: d, reasons }: { debate: ThesisDebate; reasons: PositionReason[] }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-2 rounded-md border border-[var(--border-primary)] p-2.5">
      <RunReasonLabel reasonKey={d.reason_key} reasons={reasons} />
      <span className="text-[10px] text-[var(--text-ghost)]">{new Date(d.created_at).toLocaleDateString()}</span>
      <div className="flex flex-col gap-2 sm:flex-row">
        <DebateSideCard title={t("thesis_bull_case_title")} colorClass="text-status-supported" side={d.bull_case} rebuttal={d.bull_rebuttal} />
        <DebateSideCard title={t("thesis_bear_case_title")} colorClass="text-status-broken" side={d.bear_case} rebuttal={d.bear_rebuttal} />
      </div>
    </div>
  )
}

// Decision Journal: shows the investor's own stated reason for buying
// (frozen alongside the rule snapshot) with two ways to challenge it,
// both through the same Evidence Gate discipline as the main Investigation
// panel -- "Attack the Thesis" (one adversarial verdict) and "Bull vs.
// Bear debate" (two evidence-grounded cases plus a rebuttal each, no
// single verdict -- the investor weighs both sides themselves). History
// persists across runs for both.
export function ThesisPanel({ positionId, thesis, reasons = [] }: { positionId: string; thesis: string; reasons?: PositionReason[] }) {
  const { t, tReason } = useTranslation()
  const { data: reviews } = useThesisReviews(positionId)
  const { data: debates } = useThesisDebates(positionId)
  const attackThesis = useAttackThesis(positionId)
  const debateThesis = useDebateThesis(positionId)
  const [attackConfirmOpen, setAttackConfirmOpen] = useState(false)
  const [debateConfirmOpen, setDebateConfirmOpen] = useState(false)
  const [attackError, setAttackError] = useState<string | null>(null)
  const [debateError, setDebateError] = useState<string | null>(null)
  // Each run challenges one reason (the agent and its Evidence Gate are
  // single-reason by design); with several, the user picks which.
  const [targetReason, setTargetReason] = useState<string>(reasons[0]?.reason_key ?? "")

  async function runAttack() {
    setAttackError(null)
    try {
      await attackThesis.mutateAsync(targetReason || undefined)
    } catch (err) {
      setAttackError(getApiErrorMessage(err, t("thesis_attack_err_default")))
    }
  }

  async function runDebate() {
    setDebateError(null)
    try {
      await debateThesis.mutateAsync(targetReason || undefined)
    } catch (err) {
      setDebateError(getApiErrorMessage(err, t("thesis_debate_err_default")))
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border border-dashed border-[var(--border-primary)] p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--text-ghost)]">
            {t("thesis_label")}
          </div>
          <p className="mt-0.5 text-sm text-[var(--text-primary)]">{thesis}</p>
        </div>
        <div className="flex flex-none items-center gap-1.5">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="gap-1.5"
            disabled={attackThesis.isPending}
            onClick={() => setAttackConfirmOpen(true)}
          >
            <Swords className="h-3.5 w-3.5" />
            {attackThesis.isPending ? t("cost_confirm_pending") : t("thesis_attack_button")}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="gap-1.5"
            disabled={debateThesis.isPending}
            onClick={() => setDebateConfirmOpen(true)}
          >
            <Users className="h-3.5 w-3.5" />
            {debateThesis.isPending ? t("cost_confirm_pending") : t("thesis_debate_button")}
          </Button>
        </div>
      </div>

      {reasons.length > 1 && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-[var(--text-muted)]">{t("thesis_target_reason")}</span>
          <Select
            value={targetReason}
            onChange={setTargetReason}
            className="flex min-w-[16rem] items-center justify-between gap-2 rounded border border-[var(--border-primary)] bg-[var(--bg-input)] px-2.5 py-1 text-xs text-[var(--text-primary)]"
            options={reasons.map((r) => ({ value: r.reason_key, label: tReason(r.reason_key, r.reason_snapshot?.description ?? r.reason_key) }))}
          />
        </div>
      )}

      {attackError && <p className="text-xs text-destructive">{attackError}</p>}
      {debateError && <p className="text-xs text-destructive">{debateError}</p>}

      {/* Newest run of each kind up front; earlier runs folded away. */}
      {reviews && reviews.length > 0 && (
        <RunHistory items={reviews} render={(r) => <ReviewCard key={r.id} review={r} reasons={reasons} />} />
      )}

      {debates && debates.length > 0 && (
        <RunHistory items={debates} render={(d) => <DebateCard key={d.id} debate={d} reasons={reasons} />} />
      )}

      <CostConfirmDialog
        open={attackConfirmOpen}
        onOpenChange={setAttackConfirmOpen}
        title={t("thesis_attack_dialog_title")}
        description={t("thesis_attack_dialog_description")}
        onConfirm={() => {
          setAttackConfirmOpen(false)
          void runAttack()
        }}
        isPending={attackThesis.isPending}
      />

      <CostConfirmDialog
        open={debateConfirmOpen}
        onOpenChange={setDebateConfirmOpen}
        title={t("thesis_debate_dialog_title")}
        description={t("thesis_debate_dialog_description")}
        onConfirm={() => {
          setDebateConfirmOpen(false)
          void runDebate()
        }}
        isPending={debateThesis.isPending}
      />
    </div>
  )
}
