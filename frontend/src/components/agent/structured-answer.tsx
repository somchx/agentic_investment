import { useState } from "react"
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, ExternalLink, HelpCircle, Info, Loader2, XCircle } from "lucide-react"
import { fetchTrace } from "@/api/conversations"
import { useTranslation } from "@/i18n/context"
import type { AgentAnswer, AgentClaim, AgentTraceDetail, EvidenceRef } from "@/types"

// Workflow 2.0 answer: plain-language sections by default, the evidence
// behind each paragraph on expand, and the full investigation trace in
// Advanced mode. Raw status codes never reach the reader as-is.

function claimLabel(c: AgentClaim, th: boolean) {
  if (!c.verified) return th ? "ยังตรวจยืนยันไม่ได้" : "Could not be verified"
  if (c.status === "SUPPORTED") return th ? "หลักฐานยืนยัน" : "Supported by evidence"
  if (c.status === "CONTRADICTED") return th ? "หลักฐานขัดแย้ง" : "Contradicted by evidence"
  return th ? "ยังไม่มีหลักฐานพอ" : "Not established yet"
}

function ClaimIcon({ c }: { c: AgentClaim }) {
  if (!c.verified || c.status === "NOT_ESTABLISHED") return <HelpCircle className="mt-0.5 h-3.5 w-3.5 flex-none text-muted-foreground" />
  if (c.status === "CONTRADICTED") return <XCircle className="mt-0.5 h-3.5 w-3.5 flex-none text-destructive" />
  return <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 flex-none text-status-supported" />
}

function sourceLabel(e: EvidenceRef, th: boolean) {
  const kind: Record<string, [string, string]> = {
    xbrl_fact: ["ตัวเลขในงบการเงิน (XBRL)", "Filed financial figure (XBRL)"],
    derived_metric: ["ค่าที่ระบบคำนวณจากงบการเงิน", "Computed from filed figures"],
    filing_passage: ["ข้อความในรายงาน", "Filing passage"],
    filing_record: ["รายการเอกสารที่ยื่น SEC", "SEC filing record"],
    price_quote: ["ราคาหุ้น", "Price quote"],
    portfolio_record: ["บันทึกการซื้อของคุณ", "Your purchase records"],
    thesis_snapshot: ["เหตุผล ณ วันที่ซื้อ", "Reason as recorded at purchase"],
  }
  const [t, e2] = kind[e.kind] ?? [e.kind, e.kind]
  const parts = [th ? t : e2, e.form, e.period_end && (th ? `งวด ${e.period_end}` : `period ${e.period_end}`), e.filed && (th ? `เผยแพร่ ${e.filed}` : `published ${e.filed}`)]
  return parts.filter(Boolean).join(" · ")
}

function EvidenceItem({ e, th }: { e: EvidenceRef; th: boolean }) {
  return (
    <li className="rounded-md border border-[var(--border-secondary)] bg-[var(--bg-card)] p-2 text-xs">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[var(--text-muted)]">
        <span>{sourceLabel(e, th)}</span>
        {e.accession_number && <span className="font-mono-num">{e.accession_number}</span>}
        {e.source_url && (
          <a href={e.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-primary hover:underline">
            {th ? "เปิดเอกสาร" : "Open source"} <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
      {e.excerpt && <p className="mt-1 line-clamp-4 text-[var(--text-primary)]">{e.excerpt}</p>}
    </li>
  )
}

function ParagraphEvidence({ claims, th }: { claims: AgentClaim[]; th: boolean }) {
  const [open, setOpen] = useState(false)
  if (!claims.length) return null
  const sources = claims.reduce((n, c) => n + c.evidence.length, 0)
  return (
    <div className="mt-1">
      <button type="button" onClick={() => setOpen(o => !o)} className="inline-flex items-center gap-1 text-[11px] text-[var(--text-muted)] hover:text-[var(--text-primary)]">
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {th ? `ดูหลักฐาน (${sources} แหล่ง)` : `Show evidence (${sources} sources)`}
      </button>
      {open && (
        <ul className="mt-1.5 space-y-2 border-l-2 border-[var(--border-primary)] pl-3">
          {claims.map(c => (
            <li key={c.claim_id} className="space-y-1.5">
              <div className="flex items-start gap-1.5 text-xs">
                <ClaimIcon c={c} />
                <span><span className="font-medium">{claimLabel(c, th)}:</span> {c.proposition}</span>
              </div>
              {c.quoted_span && <blockquote className="border-l-2 border-primary/40 pl-2 text-xs italic text-[var(--text-muted)]">“{c.quoted_span}”</blockquote>}
              <ul className="space-y-1.5">{c.evidence.map(e => <EvidenceItem key={e.evidence_id} e={e} th={th} />)}</ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const STOP_REASON: Record<string, [string, string]> = {
  FINALIZED: ["ตรวจครบและผ่านการตรวจหลักฐาน", "Completed and passed evidence checks"],
  BUDGET_EXHAUSTED: ["หยุดเพราะครบงบการค้นหา", "Stopped at the search budget"],
  GATE_REJECTIONS_EXHAUSTED: ["บางส่วนตรวจหลักฐานไม่ผ่านและถูกตัดออก", "Some content failed evidence checks and was removed"],
}

function AdvancedTrace({ traceId, th }: { traceId: number; th: boolean }) {
  const [open, setOpen] = useState(false)
  const [trace, setTrace] = useState<AgentTraceDetail | null>(null)
  const [error, setError] = useState(false)
  async function toggle() {
    setOpen(o => !o)
    if (!trace && !error) {
      try { setTrace(await fetchTrace(traceId)) } catch { setError(true) }
    }
  }
  const cfg = trace?.config as Record<string, string> | undefined
  return (
    <div className="mt-2">
      <button type="button" onClick={toggle} className="inline-flex items-center gap-1 text-[11px] text-[var(--text-ghost)] hover:text-[var(--text-primary)]">
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {th ? "ขั้นสูง: เส้นทางการตรวจสอบ" : "Advanced: investigation trace"}
      </button>
      {open && (
        <div className="mt-1.5 space-y-2 rounded-md border border-[var(--border-primary)] bg-[var(--bg-hover)] p-3 text-[11px]">
          {!trace && !error && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {error && <p className="text-destructive">{th ? "โหลดเส้นทางการตรวจสอบไม่ได้" : "Could not load the trace"}</p>}
          {trace && (
            <>
              <p className="font-mono-num text-[var(--text-muted)]">
                intent={trace.intent} · workflow {cfg?.workflow_version} · tools {cfg?.tool_schema_version} · gate {cfg?.evidence_gate_version} · prompt {cfg?.prompt_version} ({cfg?.prompt_hash}) · {cfg?.model}
              </p>
              <p className="font-mono-num text-[var(--text-muted)]">
                stop={trace.stop_reason} · tokens {trace.usage.input_tokens}/{trace.usage.output_tokens} · {((trace.latency_ms ?? 0) / 1000).toFixed(1)}s · ${trace.cost_usd?.toFixed(4)} · LLM calls {trace.trace.llm_calls.length} · retrieval rounds {trace.trace.retrieval_iterations} · gate rejections {trace.trace.gate_rejections.length}
              </p>
              <ol className="list-decimal space-y-0.5 pl-4 font-mono-num">
                {trace.trace.tool_calls.map((c, i) => (
                  <li key={i} className={c.error ? "text-destructive" : undefined}>
                    {c.name}({Object.entries(c.input).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")}) · {c.latency_ms}ms{c.evidence_ids.length ? ` · ${c.evidence_ids.join(" ")}` : ""}{c.error ? ` · ${c.error}` : ""}
                  </li>
                ))}
              </ol>
              {trace.trace.assessments.map((a, i) => (
                <p key={i}>{a.topic}: {a.sufficiency} · + {a.supporting_evidence_ids.join(" ") || "—"} · − {a.contradicting_evidence_ids.join(" ") || "—"}</p>
              ))}
              {trace.trace.gate_rejections.map((r, i) => (
                <details key={i}><summary>{th ? `ถูกตีกลับรอบที่ ${i + 1}` : `Rejection ${i + 1}`}</summary><ul className="list-disc pl-4">{r.problems.map((p, j) => <li key={j}>{p}</li>)}</ul></details>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export function StructuredAnswer({ answer, traceId }: { answer: AgentAnswer; traceId?: number }) {
  const { lang } = useTranslation()
  const th = lang === "th"
  const claims = Object.fromEntries(answer.claims.map(c => [c.claim_id, c]))
  const stop = answer.stop_reason ? STOP_REASON[answer.stop_reason] : undefined
  return (
    <div className="space-y-4 text-sm leading-relaxed text-[var(--text-primary)]">
      {answer.sections.map(s => (
        <section key={s.key} className="space-y-2">
          <h3 className="text-sm font-semibold">{s.title}</h3>
          {s.paragraphs.map((p, i) => (
            <div key={i}>
              <p>{p.text}</p>
              <ParagraphEvidence claims={p.claim_ids.map(id => claims[id]).filter(Boolean)} th={th} />
            </div>
          ))}
        </section>
      ))}
      {answer.system_notes.length > 0 && (
        <div className="flex items-start gap-2 rounded-md border border-[var(--border-primary)] bg-[var(--bg-hover)] p-3 text-xs text-[var(--text-muted)]">
          {answer.stop_reason === "FINALIZED" ? <Info className="mt-0.5 h-3.5 w-3.5 flex-none" /> : <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-none" />}
          <ul className="space-y-1">{answer.system_notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </div>
      )}
      {answer.scope_note && <p className="text-xs italic text-[var(--text-muted)]">{answer.scope_note}</p>}
      <p className="text-[11px] text-[var(--text-ghost)]">
        {th ? `ข้อมูล ณ ${answer.analysis_date}` : `Data as of ${answer.analysis_date}`}
        {stop && ` · ${th ? stop[0] : stop[1]}`}
      </p>
      {traceId !== undefined && <AdvancedTrace traceId={traceId} th={th} />}
    </div>
  )
}
