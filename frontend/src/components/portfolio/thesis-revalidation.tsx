import { useEffect, useRef, useState } from "react"
import { ArrowRight, CalendarClock, ExternalLink, FileSearch, Info, ListChecks, Search, ShieldCheck, Telescope } from "lucide-react"
import { StatusBadge } from "@/components/status-badge"
import { formatRatio, formatRule } from "@/components/dashboard/reason-trend-chart"
import { useRevalidation } from "@/hooks/use-positions"
import { useLatestInvestigation } from "@/hooks/use-report"
import { useTranslation } from "@/i18n/context"
import { cn } from "@/lib/utils"
import type { AgentToolCall, InvestigationReport, ReasonRevalidation, ReasonStatus, RevalidationPoint, RevalidationSource } from "@/types"

// Thesis Revalidation: for each reason of one purchase, the thesis at purchase
// -> what changed -> what the agent checked -> what is still unknown -> what to
// watch next. Everything except the Evidence Trail is mechanical and free
// (GET /positions/{id}/revalidation); the trail reads the stored AI Summary's
// recorded tool calls -- nothing here calls the LLM.

const STATUS_DOT: Record<ReasonStatus, string> = {
  Supported: "bg-status-supported",
  Weakened: "bg-status-weakened",
  Broken: "bg-status-broken",
  "Not enough data": "bg-status-unknown",
}

export function formatMoney(value: number, unit = "USD") {
  if (unit !== "USD") return `${value.toLocaleString()} ${unit}`
  const abs = Math.abs(value)
  const sign = value < 0 ? "−" : ""
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`
  return `${sign}$${abs.toLocaleString()}`
}

function Section({ icon: Icon, title, children }: { icon: typeof Info; title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]">
        <Icon className="h-3.5 w-3.5 text-primary" />
        {title}
      </h4>
      {children}
    </div>
  )
}

function SourceList({ sources }: { sources: RevalidationSource[] }) {
  const { t } = useTranslation()
  return (
    <ul className="flex flex-col gap-1 text-[11px] text-[var(--text-muted)]">
      {sources.map((s) => (
        <li key={`${s.accession_number}-${s.metric}-${s.period_end}`} className="flex flex-wrap items-center gap-x-1.5">
          <span className="font-mono-num text-[var(--text-primary)]">{s.metric} {s.period_end} = {formatMoney(s.value, s.unit)}</span>
          <span>· {s.form} · {t("reval_filed", { date: s.filed })} · {s.accession_number}</span>
          {s.url && (
            <a href={s.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 text-primary hover:underline">
              EDGAR <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </li>
      ))}
    </ul>
  )
}

// What the raw numbers behind a ratio are, and how they moved since purchase.
function RawAmounts({ r }: { r: ReasonRevalidation }) {
  const { t } = useTranslation()
  const now = r.delta?.now ?? []
  if (now.length < 2) return null
  if (r.kind === "yoy_growth") {
    const [cur, prior] = now
    const diff = cur.value - prior.value
    return (
      <p className="text-xs text-[var(--text-secondary)]">
        {t("reval_raw_growth", {
          metric: cur.metric, period: cur.period_end, value: formatMoney(cur.value, cur.unit),
          prior_period: prior.period_end, prior_value: formatMoney(prior.value, prior.unit),
        })}{" "}
        <span className={cn("font-mono-num font-semibold", diff >= 0 ? "text-[var(--text-primary)]" : "text-[var(--text-primary)]")}>
          (Δ {diff >= 0 ? "+" : ""}{formatMoney(diff, cur.unit)})
        </span>
      </p>
    )
  }
  const [num, den] = now
  return (
    <p className="text-xs text-[var(--text-secondary)]">
      {t("reval_raw_margin", { num_metric: num.metric, num: formatMoney(num.value, num.unit), den_metric: den.metric, den: formatMoney(den.value, den.unit), period: num.period_end })}
    </p>
  )
}

function Timeline({ points, selected, onSelect }: { points: RevalidationPoint[]; selected: number; onSelect: (i: number) => void }) {
  const { t } = useTranslation()
  const scrollRef = useRef<HTMLDivElement>(null)
  // Open scrolled to the newest point, which is what's selected by default.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollLeft = el.scrollWidth
  }, [points.length])
  return (
    <div ref={scrollRef} className="overflow-x-auto pb-1">
      <ol className="flex min-w-max items-start">
        {points.map((p, i) => (
          <li key={`${p.as_of}-${i}`} className="flex items-start">
            {i > 0 && <span className={cn("mt-[11px] h-px w-10 sm:w-14", p.before_purchase ? "bg-[var(--border-primary)]" : "bg-primary/40")} />}
            <button
              type="button"
              onClick={() => onSelect(i)}
              aria-pressed={i === selected}
              className={cn(
                "flex w-[88px] flex-col items-center gap-0.5 rounded-md px-1 py-0.5 text-center transition-colors hover:bg-[var(--bg-hover)]",
                i === selected && "bg-primary/10",
                p.before_purchase && "opacity-60",
              )}
            >
              <span className={cn("h-3 w-3 rounded-full ring-2 ring-[var(--bg-card)]", STATUS_DOT[p.status], i === selected && "h-3.5 w-3.5 ring-primary/40")} />
              <span className="font-mono-num text-[11px] font-semibold text-[var(--text-primary)]">{p.value != null ? formatRatio(p.value) : "—"}</span>
              <span className="font-mono-num text-[10px] text-[var(--text-muted)]">{p.as_of}</span>
              <span className="text-[10px] text-[var(--text-ghost)]">
                {p.is_purchase_date ? t("reval_point_purchase") : p.before_purchase ? t("reval_point_before") : t("reval_point_filing")}
              </span>
            </button>
          </li>
        ))}
      </ol>
      {points.some((p) => p.before_purchase) && (
        <p className="mt-1.5 text-[10px] text-[var(--text-ghost)]">{t("reval_history_note")}</p>
      )}
    </div>
  )
}

function PointDetail({ p }: { p: RevalidationPoint }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-1.5 rounded-md border border-[var(--border-primary)] bg-[var(--bg-hover)]/40 p-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-semibold text-[var(--text-primary)]">
          {t("reval_known_at", { date: p.as_of })}
          {p.before_purchase && <span className="ml-1.5 font-normal text-[var(--text-muted)]">· {t("reval_history_label")}</span>}
        </span>
        <StatusBadge status={p.status} />
      </div>
      <p className="text-[11px] text-[var(--text-secondary)]">{p.explanation}</p>
      {p.conflicting_versions > 0 && (
        <p className="text-[11px] text-status-weakened">{t("reval_conflicting_versions", { count: p.conflicting_versions })}</p>
      )}
      {p.sources.length > 0 && <SourceList sources={p.sources} />}
    </div>
  )
}

// One readable line per recorded tool call that concerns this reason.
function TrailStep({ call, index, evaluatedPeriod }: { call: AgentToolCall; index: number; evaluatedPeriod?: string | null }) {
  const { t } = useTranslation()
  const r = call.result ?? {}
  let title = call.name
  let finding: React.ReactNode = null
  let extra: React.ReactNode = null
  if (call.name === "check_reason_status" || call.name === "calculate_metric") {
    title = t(call.name === "check_reason_status" ? "trail_check_status" : "trail_calculate", { date: String(call.input.as_of ?? "") })
    finding = r.error
      ? String(r.error)
      : `${r.status ? `${r.status} · ` : ""}${typeof r.computed_value === "number" ? formatRatio(r.computed_value) : typeof r.value === "number" ? formatRatio(r.value as number) : ""}`
  } else if (call.name === "get_secondary_evidence") {
    title = t("trail_secondary")
    if (r.period_matches === false)
      // Newer runs: the tool itself reports that it found another period's release.
      finding = t("trail_secondary_other_period", { checked: String(r.release_period_end ?? "?"), evaluated: String(r.target_period ?? "?") })
    else if (r.checked === false) finding = t("trail_secondary_unchecked", { reason: String(r.reason ?? "") })
    else if (typeof r.filed_value === "number" && typeof r.earnings_release_value === "number") {
      finding = t(r.conflict ? "trail_secondary_conflict" : "trail_secondary_match", {
        filed: formatMoney(r.filed_value as number), release: formatMoney(r.earnings_release_value as number),
        diff: typeof r.diff_pct === "number" ? (r.diff_pct as number).toFixed(2) : "?",
        period: String(r.period_end ?? "?"),
      })
      // The cross-check only verifies the period it found a release for, which
      // isn't always the quarter the rule was evaluated on -- say so plainly.
      if (evaluatedPeriod && r.period_end && r.period_end !== evaluatedPeriod)
        extra = (
          <p className="mt-0.5 text-[11px] text-status-weakened">
            {t("trail_secondary_other_period", { checked: String(r.period_end), evaluated: evaluatedPeriod })}
          </p>
        )
    }
  } else if (call.name === "get_filing_context") {
    title = t("trail_filing_context")
    const excerpts = Array.isArray(r.narrative_excerpts) ? (r.narrative_excerpts as string[]) : []
    finding = r.found ? t("trail_filing_found", { count: excerpts.length }) : t("trail_filing_not_found")
    if (excerpts.length)
      extra = (
        <details className="mt-1">
          <summary className="cursor-pointer text-[11px] text-primary">{t("trail_show_excerpts")}</summary>
          <div className="mt-1 flex flex-col gap-1.5">
            {excerpts.map((e, i) => (
              <blockquote key={i} className="border-l-2 border-primary/40 pl-2 text-[11px] text-[var(--text-muted)]">{e}</blockquote>
            ))}
          </div>
        </details>
      )
  } else if (call.name === "web_search") {
    title = t("trail_web_search")
  }
  return (
    <li className="flex gap-2.5">
      <span className="mt-0.5 grid h-5 w-5 flex-none place-items-center rounded-full bg-primary/15 font-mono-num text-[10px] font-semibold text-primary">{index}</span>
      <div className="min-w-0">
        <p className="text-xs font-medium text-[var(--text-primary)]">{title}</p>
        {finding && <p className="text-[11px] text-[var(--text-muted)]">→ {finding}</p>}
        {extra}
      </div>
    </li>
  )
}

function EvidenceTrail({ reasonKey, summary, evaluatedPeriod }: { reasonKey: string; summary: InvestigationReport | null | undefined; evaluatedPeriod?: string | null }) {
  const { t } = useTranslation()
  if (!summary) return <p className="text-xs text-[var(--text-muted)]">{t("trail_no_summary")}</p>
  const calls = (summary.tool_calls ?? []).filter((c) => c.input?.reason_key === reasonKey)
  const gateRejections = summary.trace.filter((l) => l.includes("rejected") && l.includes(reasonKey))
  const conclusion = summary.reasons.find((r) => r.reason_key === reasonKey)
  if (!summary.tool_calls)
    return <p className="text-xs text-[var(--text-muted)]">{t("trail_old_summary")}</p>
  if (calls.length === 0)
    return <p className="text-xs text-[var(--text-muted)]">{t("trail_not_covered")}</p>
  return (
    <div className="flex flex-col gap-2">
      <ol className="flex flex-col gap-2">
        {calls.map((c, i) => <TrailStep key={i} call={c} index={i + 1} evaluatedPeriod={evaluatedPeriod} />)}
      </ol>
      {gateRejections.length > 0 && (
        <p className="flex items-start gap-1.5 text-[11px] text-status-weakened">
          <ShieldCheck className="mt-0.5 h-3 w-3 flex-none" />
          {t("trail_gate_rejected", { count: gateRejections.length })}
        </p>
      )}
      {conclusion && (
        <div className="flex flex-wrap items-center gap-2 border-t border-[var(--border-primary)]/60 pt-2 text-[11px] text-[var(--text-muted)]">
          <span>{t("trail_conclusion")}</span>
          <StatusBadge status={conclusion.status} />
          <span>{t("investigate_confidence", { confidence: t(`confidence_${conclusion.confidence}`) })}</span>
          {conclusion.human_review_recommended && <span className="text-status-weakened">{t("investigate_review_recommended")}</span>}
        </div>
      )}
      {summary.generated_at && (
        <p className="text-[10px] text-[var(--text-ghost)]">{t("trail_from_summary", { date: new Date(summary.generated_at).toLocaleString() })}</p>
      )}
    </div>
  )
}

function MonitorNext({ r }: { r: ReasonRevalidation }) {
  const { t } = useTranslation()
  const m = r.monitor
  if (!m) return null
  const rule = formatRule(m.comparison, m.threshold)
  return (
    <div className="flex flex-col gap-1.5 text-xs text-[var(--text-secondary)]">
      {m.kind === "yoy_growth" && m.next_base && m.required_value != null ? (
        <p>
          {t("monitor_growth_requirement", {
            metric: m.next_base.metric, op: rule.split(" ")[0], required: formatMoney(m.required_value, m.next_base.unit),
            base_period: m.next_base.period_end, base_value: formatMoney(m.next_base.value, m.next_base.unit), rule,
          })}
        </p>
      ) : (
        <p>{t("monitor_level_requirement", { rule })}</p>
      )}
      {m.estimated_next_filing && (
        <p className="flex items-center gap-1.5 text-[var(--text-muted)]">
          <CalendarClock className="h-3.5 w-3.5 text-primary" />
          {t("monitor_next_checkpoint", { date: m.estimated_next_filing })}
        </p>
      )}
    </div>
  )
}

function ReasonRevalidationBlock({ r, summary }: { r: ReasonRevalidation; summary: InvestigationReport | null | undefined }) {
  const { t, tReason } = useTranslation()
  const points = r.timeline ?? []
  const purchaseIdx = Math.max(0, points.findIndex((p) => p.is_purchase_date))
  const [selected, setSelected] = useState(points.length - 1)
  if (r.error || !r.now || !r.snapshot || r.comparison == null || r.threshold == null) {
    return <p className="text-xs text-[var(--text-muted)]">{tReason(r.reason_key, r.description ?? r.reason_key)}: {r.error ?? t("reval_unavailable")}</p>
  }
  const atPurchase = points[purchaseIdx]
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-[var(--border-primary)] p-3 sm:p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-[var(--text-primary)]">{tReason(r.reason_key, r.description ?? "")}</p>
          <p className="font-mono-num text-[11px] text-[var(--text-muted)]">{t("reason_chart_threshold", { rule: formatRule(r.comparison, r.threshold) })}</p>
        </div>
        <StatusBadge status={r.now.status} />
      </div>

      {/* 1. Before vs now */}
      <Section icon={ArrowRight} title={t("reval_before_now")}>
        <div className="grid grid-cols-1 items-stretch gap-2 sm:grid-cols-[1fr_auto_1fr]">
          <div className="rounded-md border border-[var(--border-primary)] p-2.5">
            <p className="text-[11px] text-[var(--text-muted)]">{t("reval_at_purchase", { date: atPurchase?.as_of ?? "" })}</p>
            <p className="font-mono-num text-lg font-bold text-[var(--text-primary)]">{r.snapshot.value != null ? formatRatio(r.snapshot.value) : "—"}</p>
            {r.snapshot.status && <StatusBadge status={r.snapshot.status} />}
          </div>
          <ArrowRight className="hidden h-4 w-4 self-center text-[var(--text-ghost)] sm:block" />
          <div className="rounded-md border border-primary/30 bg-primary/5 p-2.5">
            <p className="text-[11px] text-[var(--text-muted)]">{t("reval_now", { date: r.now.as_of })}</p>
            <p className="font-mono-num text-lg font-bold text-[var(--text-primary)]">{r.now.value != null ? formatRatio(r.now.value) : "—"}</p>
            <StatusBadge status={r.now.status} />
          </div>
        </div>
        <RawAmounts r={r} />
      </Section>

      {/* 2. Timeline: what the system knew at each filing */}
      <Section icon={ListChecks} title={t("reval_timeline")}>
        <Timeline points={points} selected={selected} onSelect={setSelected} />
        {points[selected] && <PointDetail p={points[selected]} />}
      </Section>

      {/* 3. What the agent checked */}
      <Section icon={FileSearch} title={t("reval_evidence_trail")}>
        <EvidenceTrail reasonKey={r.reason_key} summary={summary} evaluatedPeriod={r.now.period_end} />
      </Section>

      {/* 4. What would change this conclusion */}
      <Section icon={Telescope} title={t("reval_monitor_next")}>
        <MonitorNext r={r} />
      </Section>
    </div>
  )
}

/** All reasons of one purchase, revalidated. */
export function ThesisRevalidation({ positionId, ticker }: { positionId: string; ticker: string }) {
  const { t } = useTranslation()
  const { data, isLoading, isError } = useRevalidation(positionId)
  const { data: summary } = useLatestInvestigation(ticker)
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-dashed border-primary/30 p-3">
      <div className="flex items-center gap-2">
        <Search className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-bold text-[var(--text-primary)]">{t("reval_title")}</h3>
      </div>
      <p className="flex items-start gap-1.5 text-[11px] text-[var(--text-muted)]">
        <Info className="mt-0.5 h-3 w-3 flex-none" />
        {t("reval_point_in_time_note")}
      </p>
      {isLoading && <p className="text-xs text-[var(--text-muted)]">{t("reval_loading")}</p>}
      {isError && <p className="text-xs text-destructive">{t("reval_error")}</p>}
      {data?.reasons.map((r) => <ReasonRevalidationBlock key={r.reason_key} r={r} summary={summary} />)}
    </div>
  )
}
