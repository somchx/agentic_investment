import { useState } from "react"
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Loader2, ShieldCheck, Sparkles, Wrench, XCircle } from "lucide-react"
import { useTranslation } from "@/i18n/context"
import { cn } from "@/lib/utils"
import type { AgentProgressEvent } from "@/types"

// What the agent is doing, live: one row per step built from the streamed
// progress events (question analysis, each Claude round, each tool call with
// its JSON input/output, Evidence Gate decisions). Display only.

const TOOL_LABELS: Record<string, [string, string]> = {
  get_user_portfolio: ["ดึงข้อมูลพอร์ต", "Load portfolio"],
  get_holdings: ["ดึงรายการถือครอง", "Load holdings"],
  get_purchase_transactions: ["ดึงรายการซื้อ", "Load purchases"],
  get_original_thesis_snapshot: ["ดูเหตุผล ณ วันที่ซื้อ", "Read reasons at purchase"],
  get_confirmed_thesis_claims: ["ดูเหตุผลที่ยืนยันไว้", "Read confirmed reasons"],
  get_latest_thesis_evaluations: ["ตรวจเหตุผลกับงบล่าสุด", "Check reasons on latest filings"],
  get_historical_evaluations: ["ไล่ผลย้อนหลังตามงวด", "Re-check past periods"],
  get_verified_financial_metrics: ["ดึงตัวเลขงบการเงิน", "Fetch financial figures"],
  compare_financial_periods: ["เทียบตอนซื้อกับปัจจุบัน", "Compare purchase vs now"],
  check_new_sec_filings: ["หาเอกสาร SEC ใหม่", "Look for new SEC filings"],
  retrieve_filing_evidence: ["อ่านคำอธิบายในรายงาน (MD&A)", "Read MD&A passages"],
  search_filing_sections: ["ค้นข้อความในรายงาน", "Search filing text"],
  get_investigation_trace: ["ดูการตรวจครั้งก่อน", "Read earlier investigations"],
  get_evidence_assessment: ["ดูผลประเมินที่บันทึกไว้", "Read stored assessments"],
  get_secondary_evidence: ["เทียบกับ earnings release", "Cross-check earnings release"],
  record_evidence_assessment: ["บันทึกการประเมินหลักฐาน", "Record evidence assessment"],
  finalize_answer: ["ส่งคำตอบให้ Evidence Gate ตรวจ", "Submit answer to the Evidence Gate"],
}

type Row =
  | { kind: "intent"; e: AgentProgressEvent }
  | { kind: "llm"; call: number; purpose?: string; end?: AgentProgressEvent }
  | { kind: "tool"; start: AgentProgressEvent; end?: AgentProgressEvent }
  | { kind: "gate"; e: AgentProgressEvent }

function buildRows(events: AgentProgressEvent[]): Row[] {
  const rows: Row[] = []
  for (const e of events) {
    if (e.type === "intent") rows.push({ kind: "intent", e })
    else if (e.type === "llm_start") rows.push({ kind: "llm", call: e.call ?? rows.length, purpose: e.purpose })
    else if (e.type === "llm_end") {
      const r = [...rows].reverse().find((x): x is Extract<Row, { kind: "llm" }> => x.kind === "llm" && x.call === e.call)
      if (r) r.end = e
    } else if (e.type === "tool_start") rows.push({ kind: "tool", start: e })
    else if (e.type === "tool_end") {
      const r = rows.find((x): x is Extract<Row, { kind: "tool" }> => x.kind === "tool" && x.start.id === e.id)
      if (r) r.end = e
    } else if (["gate_rejected", "gate_accepted", "gate_gave_up", "budget_exhausted"].includes(e.type)) rows.push({ kind: "gate", e })
  }
  return rows
}

function Json({ value }: { value: unknown }) {
  return <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded bg-[var(--bg-card)] p-2 font-mono-num text-[10px] leading-snug text-[var(--text-muted)]">{JSON.stringify(value, null, 2)}</pre>
}

function ToolRow({ row, th }: { row: Extract<Row, { kind: "tool" }>; th: boolean }) {
  const [open, setOpen] = useState(false)
  const name = row.start.name ?? ""
  const label = TOOL_LABELS[name]
  const running = !row.end
  const failed = !!row.end?.error
  const args = row.start.input && Object.keys(row.start.input).length ? JSON.stringify(row.start.input) : ""
  return (
    <li>
      <button type="button" onClick={() => setOpen(o => !o)} disabled={running} className="flex w-full items-start gap-2 text-left">
        {running ? <Loader2 className="mt-0.5 h-3.5 w-3.5 flex-none animate-spin text-primary" />
          : failed ? <XCircle className="mt-0.5 h-3.5 w-3.5 flex-none text-destructive" />
          : <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 flex-none text-status-supported" />}
        <span className="min-w-0 flex-1">
          <span className="font-medium text-[var(--text-primary)]">{label ? (th ? label[0] : label[1]) : name}</span>{" "}
          <span className="font-mono-num text-[var(--text-muted)]">{name}{args && ` ${args}`}</span>
          {row.end && (
            <span className="ml-1 text-[var(--text-ghost)]">
              · {row.end.latency_ms}ms
              {row.end.evidence_ids?.length ? ` · ${th ? "หลักฐาน" : "evidence"} ${row.end.evidence_ids.length}` : ""}
              {failed ? ` · ${row.end.error}` : ""}
            </span>
          )}
        </span>
        {!running && (open ? <ChevronDown className="mt-0.5 h-3 w-3 flex-none" /> : <ChevronRight className="mt-0.5 h-3 w-3 flex-none" />)}
      </button>
      {open && row.end && (
        <div className="ml-5">
          <p className="mt-1 text-[10px] uppercase tracking-wider text-[var(--text-ghost)]">input</p>
          <Json value={row.start.input ?? {}} />
          <p className="mt-1 text-[10px] uppercase tracking-wider text-[var(--text-ghost)]">output</p>
          <Json value={row.end.output} />
        </div>
      )}
    </li>
  )
}

function StepList({ rows, th }: { rows: Row[]; th: boolean }) {
  return (
    <ol className="space-y-1.5 text-xs">
      {rows.map((r, i) => {
        if (r.kind === "intent") {
          return (
            <li key={i} className="flex items-start gap-2">
              <Sparkles className="mt-0.5 h-3.5 w-3.5 flex-none text-primary" />
              <span>
                <span className="font-medium">{th ? "วิเคราะห์คำถาม" : "Question analysed"}:</span>{" "}
                <span className="font-mono-num">{r.e.intent}</span>
                {r.e.required_tools?.length ? <span className="text-[var(--text-muted)]"> · {th ? "ต้องตรวจ" : "required"}: {r.e.required_tools.join(", ")}</span> : null}
              </span>
            </li>
          )
        }
        if (r.kind === "llm") {
          const running = !r.end
          const writing = r.purpose === "finalize" || r.end?.next_tools?.includes("finalize_answer")
          const label = running
            ? (r.purpose === "finalize" ? (th ? "Claude กำลังเรียบเรียงคำตอบ…" : "Claude is writing the answer…") : (th ? `Claude กำลังคิด (รอบ ${r.call})…` : `Claude is thinking (round ${r.call})…`))
            : writing ? (th ? `Claude เขียนคำตอบเสร็จ (รอบ ${r.call})` : `Claude wrote the answer (round ${r.call})`)
            : (th ? `Claude วางแผนเสร็จ (รอบ ${r.call})` : `Claude planned (round ${r.call})`)
          return (
            <li key={i} className="flex items-start gap-2">
              {running ? <Loader2 className="mt-0.5 h-3.5 w-3.5 flex-none animate-spin text-primary" /> : <Wrench className="mt-0.5 h-3.5 w-3.5 flex-none text-[var(--text-muted)]" />}
              <span className="min-w-0">
                <span className={cn("font-medium", running && "text-primary")}>{label}</span>
                {r.end && <span className="text-[var(--text-ghost)]"> · {(r.end.latency_ms ?? 0) / 1000}s</span>}
                {r.end?.next_tools?.length ? <span className="text-[var(--text-muted)]"> · {th ? "เลือก" : "chose"}: {r.end.next_tools.join(", ")}</span> : null}
                {r.end?.text && <span className="mt-0.5 block italic text-[var(--text-muted)]">“{r.end.text}”</span>}
              </span>
            </li>
          )
        }
        if (r.kind === "tool") return <ToolRow key={r.start.id ?? i} row={r} th={th} />
        const e = r.e
        const ok = e.type === "gate_accepted"
        return (
          <li key={i} className={cn("flex items-start gap-2", ok ? "text-status-supported" : "text-destructive")}>
            {ok ? <ShieldCheck className="mt-0.5 h-3.5 w-3.5 flex-none" /> : <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-none" />}
            <span>
              <span className="font-medium">
                {e.type === "gate_accepted" ? (th ? "ผ่าน Evidence Gate" : "Passed the Evidence Gate")
                  : e.type === "gate_rejected" ? (th ? "Evidence Gate ตีกลับให้แก้" : "Evidence Gate sent it back")
                  : e.type === "gate_gave_up" ? (th ? "แก้ไม่ผ่าน ตัดส่วนที่ไม่มีหลักฐานออก" : "Still failing; unsupported parts removed")
                  : (th ? "ครบงบการค้นหา บังคับสรุป" : "Search budget used up; finalizing")}
              </span>
              {e.problems?.length ? <ul className="mt-0.5 list-disc pl-4 text-[var(--text-muted)]">{e.problems.map((p, j) => <li key={j}>{p}</li>)}</ul> : null}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function Counters({ events, th }: { events: AgentProgressEvent[]; th: boolean }) {
  const c = [...events].reverse().find(e => e.counters)?.counters
  if (!c) return null
  return (
    <p className="font-mono-num text-[10px] text-[var(--text-ghost)]">
      {th ? "เครื่องมือ" : "tools"} {c.tool_calls}/{c.max_tool_calls} · tokens {c.input_tokens.toLocaleString()}/{c.output_tokens.toLocaleString()} · {(c.elapsed_ms / 1000).toFixed(0)}s
    </p>
  )
}

/** Live view while the agent runs. */
export function AgentProgress({ events }: { events: AgentProgressEvent[] }) {
  const { lang } = useTranslation()
  const th = lang === "th"
  return (
    <div role="status" aria-live="polite" className="space-y-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-hover)] p-3">
      <p className="flex items-center gap-2 text-sm font-semibold">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        {th ? "Agent กำลังตรวจสอบ" : "The agent is investigating"}
      </p>
      {events.length <= 1 ? <p className="text-xs text-[var(--text-muted)]">{th ? "กำลังเริ่ม…" : "Starting…"}</p> : <StepList rows={buildRows(events)} th={th} />}
      <Counters events={events} th={th} />
    </div>
  )
}

/** Collapsed record of the steps under a finished answer. */
export function AgentProgressLog({ events }: { events: AgentProgressEvent[] }) {
  const { lang } = useTranslation()
  const th = lang === "th"
  const [open, setOpen] = useState(false)
  const rows = buildRows(events)
  const tools = rows.filter(r => r.kind === "tool").length
  return (
    <div>
      <button type="button" onClick={() => setOpen(o => !o)} className="inline-flex items-center gap-1 text-[11px] text-[var(--text-ghost)] hover:text-[var(--text-primary)]">
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {th ? `ขั้นตอนการทำงาน (${tools} เครื่องมือ)` : `Steps taken (${tools} tools)`}
      </button>
      {open && <div className="mt-1.5 space-y-2 rounded-md border border-[var(--border-primary)] bg-[var(--bg-hover)] p-3"><StepList rows={rows} th={th} /><Counters events={events} th={th} /></div>}
    </div>
  )
}
