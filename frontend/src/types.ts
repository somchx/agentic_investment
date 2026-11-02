// Shared TypeScript interfaces mirroring the FastAPI backend contract
// (see project README / task spec for the authoritative REST contract).

export interface User {
  id: number
  email: string
  full_name: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Company {
  ticker: string
  name: string
}

// Must match what src/db.py's save_reason() actually validates:
// comparison in ('>','>=','<','<='), kind in ('yoy_growth','margin_level').
export type ComparisonOp = ">" | ">=" | "<" | "<="

export type ReasonKind = "yoy_growth" | "margin_level"

export interface RuleDefinition {
  version: number
  preset: string
  evaluation_period: 'quarterly' | 'annual' | 'user_selected_window'
  thesis_type?: 'NATURAL_LANGUAGE'
  thesis_clarity?: 'CONFIRMED' | 'NEEDS_CLARIFICATION' | 'EXPLORATORY'
  thesis_version_id?: string
  version_no?: number
  company?: string
  confirmed_interpretation?: {claims: NaturalClaim[]}
  mode?: string
  preview?: string
  unit?: string
}
export interface RuleEvaluationFields {
  rule_definition?: RuleDefinition | null
  original_text?: string
  rule_status?: 'SATISFIED' | 'BREACHED' | 'NOT_EVALUATED'
  evidence_status?: 'SUFFICIENT' | 'CONFLICTING' | 'INSUFFICIENT' | 'NOT_YET_OBSERVABLE'
  value_unit?: string
  comparison_value?: number | null
}

export interface Reason extends RuleEvaluationFields {
  reason_key: string
  ticker: string
  metric: string
  comparison: ComparisonOp
  threshold: number | null
  kind: ReasonKind
  denominator_metric?: string | null
  description: string
  instant: boolean
  is_builtin: boolean
}

export interface CreateReasonPayload {
  reason_key: string
  // Omit (or null) to create a global reason -- applies to every company,
  // same as a built-in one, instead of just this ticker.
  ticker?: string | null
  metric: string
  comparison: ComparisonOp
  threshold: number | null
  kind: ReasonKind
  denominator_metric: string
  description: string
  instant: boolean
  // Required only for a global reason (ticker omitted) -- which real
  // company to preview-evaluate it against before saving. Never stored.
  preview_ticker?: string
}

// The real shape POST /api/reasons responds with -- a preview evaluation
// of the newly-saved reason (see backend/app/api/reasons.py), not the
// Reason row itself.
export interface CreateReasonResult {
  ok: boolean
  preview: Record<string, unknown>
}

// A free, mechanical alert from continuous monitoring (backend/app/core/
// monitor.py) -- created when a held position's reason status changed
// since the last check. Never produced by the paid Investigation Agent.
export interface AppNotification {
  id: number
  ticker: string
  reason_key: string | null
  message: string
  previous_status: ReasonStatus | null
  current_status: ReasonStatus | null
  is_read: boolean
  created_at: string
  // Structured detail (null on notifications created before these existed).
  kind?: string | null
  reason_description?: string | null
  computed_value?: number | null
  previous_value?: number | null
  comparison?: ComparisonOp | null
  threshold?: number | null
  as_of?: string | null
  previous_as_of?: string | null
}

export interface XbrlTag {
  description?: string | null
  source?: { company: string; form: string; filed: string; period_end: string | null; url: string } | null
  tag: string
  label: string
  quarterly: boolean
  instant: boolean
  // Only present on the aggregated /api/xbrl-tags (no ticker) response --
  // which real companies actually report this tag.
  tickers?: string[]
  // Cached Thai translation (see backend/app/core/translate_xbrl_tags.py) --
  // null/absent for the rare tag that hasn't been translated yet.
  label_th?: string | null
}

export type ReasonStatus = "Supported" | "Weakened" | "Broken" | "Not enough data"

export interface ReportReason extends RuleEvaluationFields {
  reason_key: string
  description: string
  status: ReasonStatus
  computed_value: number | null
  as_of: string | null
  previous_status: ReasonStatus | null
  comparison?: ComparisonOp
  threshold?: number
  kind?: ReasonKind
  // Same evaluation re-run at recent filing dates, oldest first (for the trend chart).
  history?: { as_of: string; value: number; status: ReasonStatus }[]
  [key: string]: unknown
}

export interface CompanyReport {
  ticker: string
  company_name: string
  reasons: ReportReason[]
  history: unknown[]
  // When the backend last pulled this company's filings from SEC (cache refreshes every 24h).
  data_freshness?: { cached_at: string | null; age_seconds: number | null; is_stale: boolean | null }
}

export interface ToolCall {
  name: string
  arguments?: Record<string, unknown>
  result?: unknown
  [key: string]: unknown
}

export interface ChatTurn {
  role: "user" | "assistant"
  content: string
}

export interface AskAgentRequest {
  question: string
  history?: ChatTurn[]
}

export interface AskAgentResponse {
  answer: string
  tool_calls: ToolCall[]
  cost_usd: number
}

// The Structured Investigation path (agent.run_with_llm via
// POST /api/investigate/{ticker}) -- gated by the Evidence Assessor, unlike
// the free-form ask-agent chat above. Either finalize_report was accepted
// (escalated=false, reasons populated) or it was not (escalated=true,
// reasons empty, escalation_reason set -- possibly with unresolved_proposal
// for a human reviewer to look at, but never treated as an accepted result).
export interface InvestigationReasonResult extends RuleEvaluationFields {
  reason_key: string
  status: ReasonStatus
  confidence: "high" | "medium" | "low"
  human_review_recommended: boolean
  rationale: string
}

export interface InvestigationReport {
  ticker: string
  trace: string[]
  reasons: InvestigationReasonResult[]
  assessor_gaps: string[]
  escalated: boolean
  escalation_reason?: string
  unresolved_proposal?: InvestigationReasonResult[]
  usage: { input_tokens: number; output_tokens: number }
  // Every tool call the agent made (newer runs only) -- the Evidence Trail.
  tool_calls?: AgentToolCall[]
  // Set on summaries stored server-side (POST /investigate result or GET latest).
  data_as_of?: string | null
  generated_at?: string
}

export interface ChatConversationSummary {
  id: number
  title: string
  created_at: string
  updated_at: string
}

export interface ChatMessageRecord {
  id: number
  conversation_id: number
  role: "user" | "assistant"
  content: string
  cost_usd: number | null
  tool_calls_json: ToolCall[] | null
  answer_json?: AgentAnswer | null
  trace_id?: number | null
  created_at: string
}

// Workflow 2.0 structured chat answer -- every paragraph links to claims,
// every claim to evidence the backend verified (progressive disclosure).
export interface EvidenceRef {
  evidence_id: string
  kind: string
  ticker: string | null
  source: string
  accession_number: string | null
  form: string | null
  filed: string | null
  period_start: string | null
  period_end: string | null
  source_url: string | null
  locator: string | null
  excerpt: string | null
  values: number[]
  unit: string | null
}

export interface AgentClaim {
  claim_id: string
  ticker?: string
  reason_key?: string
  proposition: string
  claim_type: "numeric" | "management_attribution" | "causal_interpretation" | "uncertainty"
  status: "SUPPORTED" | "CONTRADICTED" | "NOT_ESTABLISHED"
  quoted_span?: string
  verified: boolean
  downgraded?: boolean
  evidence: EvidenceRef[]
}

export interface AgentAnswerSection {
  key: string
  title: string
  paragraphs: { text: string; claim_ids: string[] }[]
}

export interface AgentAnswer {
  intent: { intent: string; tickers: string[]; task_scope: string; required_tools: string[] }
  sections: AgentAnswerSection[]
  claims: AgentClaim[]
  scope_note: string
  system_notes: string[]
  stop_reason: string | null
  analysis_date: string
}

// Live progress event streamed while the agent works (display only).
export interface AgentProgressEvent {
  type: "started" | "intent" | "llm_start" | "llm_end" | "tool_start" | "tool_end" | "gate_rejected" | "gate_accepted" | "gate_gave_up" | "budget_exhausted" | "done" | "error"
  id?: string
  name?: string
  input?: Record<string, unknown>
  output?: unknown
  latency_ms?: number
  evidence_ids?: string[]
  error?: string | null
  call?: number
  purpose?: string
  text?: string | null
  next_tools?: string[]
  problems?: string[]
  intent?: string
  tickers?: string[]
  required_tools?: string[]
  detail?: string
  conversation_id?: number
  response?: SendMessageResponse
  counters?: { tool_calls: number; max_tool_calls: number; input_tokens: number; output_tokens: number; elapsed_ms: number }
}

export interface AgentTraceDetail {
  id: number
  created_at: string
  question: string | null
  intent: string | null
  stop_reason: string | null
  config: Record<string, unknown>
  usage: { input_tokens: number | null; output_tokens: number | null }
  latency_ms: number | null
  cost_usd: number | null
  trace: {
    tool_calls: { name: string; input: Record<string, unknown>; error?: string; latency_ms: number; evidence_ids: string[] }[]
    assessments: { topic: string; sufficiency: string; supporting_evidence_ids: string[]; contradicting_evidence_ids: string[]; open_questions?: string[] }[]
    gate_rejections: { problems: string[] }[]
    llm_calls: { latency_ms: number; input_tokens: number; output_tokens: number }[]
    verification: { claims: { claim_id: string; verified: boolean; issues: string[] }[] }
    removed_paragraphs?: string[]
    retrieval_iterations: number
  }
}

export interface ChatConversationDetail extends ChatConversationSummary {
  messages: ChatMessageRecord[]
}

export interface SendMessageRequest {
  question: string
  conversation_id?: number | null
}

export interface SendMessageResponse {
  conversation_id: number
  answer: string
  answer_structured?: AgentAnswer
  trace_id?: number
  tool_calls: ToolCall[]
  cost_usd: number
  usage?: { input_tokens: number; output_tokens: number }
  latency_ms?: number
}

export interface InvestorProfile {
  id: string
  name: string
  risk_tolerance: string
  investment_horizon: string
  position_size_pct: number
  objective: string
}

export type CreateProfilePayload = Omit<InvestorProfile, "id">

export interface PersonalizeRequest {
  profile_id: string
}

// The user's own single investor profile (budget/goals/risk tolerance),
// used to personalize the portfolio-wide chat agent -- distinct from the
// reusable named presets (InvestorProfile) above.
export interface InvestorProfileSettings {
  budget_usd: number | null
  target_growth_pct: number | null
  investment_horizon: string | null
  risk_tolerance: string | null
  goals: string | null
  notes: string | null
}

export type UpdateInvestorProfileSettingsPayload = InvestorProfileSettings

export interface PersonalizeResponse {
  ticker: string
  priority: string | number
  rationale?: string
  cost_usd: number
  [key: string]: unknown
}

export interface ScreenReasonResult extends RuleEvaluationFields {
  description?: string
  status?: ReasonStatus
  computed_value?: number | null
  as_of?: string | null
  error?: string
}

export interface ScreenCompany {
  ticker: string
  company_name: string
  by_reason: Record<string, ScreenReasonResult>
}

export interface ScreenResult {
  reason_keys: string[]
  companies: ScreenCompany[]
}

export interface ReasonSnapshot extends RuleEvaluationFields {
  description: string
  status_at_purchase: ReasonStatus
  computed_value_at_purchase: number | null
  explanation_at_purchase?: string
  [key: string]: unknown
}

export interface Position {
  id: string
  ticker: string
  quantity: number
  purchase_price: number
  purchase_date: string
  // First attached reason (legacy single-reason fields); see `reasons`.
  reason_key: string | null
  reason_snapshot: ReasonSnapshot | null
  // Every reason this purchase was made for, each frozen at the purchase date.
  reasons: PositionReason[]
  // Decision Journal: the investor's own free-text WHY, frozen alongside
  // the WHAT in reason_snapshot.
  thesis: string | null
}

export interface AgentToolCall {
  name: string
  input: Record<string, unknown>
  result: Record<string, unknown>
}

// GET /positions/{id}/revalidation -- mechanical, point-in-time.
export interface RevalidationSource {
  metric: string
  period_end: string
  value: number
  unit: string
  form: string
  filed: string
  accession_number: string
  url: string
}

export interface RevalidationPoint extends RuleEvaluationFields {
  as_of: string
  status: ReasonStatus
  value: number | null
  period_end: string | null
  explanation: string
  sources: RevalidationSource[]
  conflicting_versions: number
  before_purchase: boolean
  is_purchase_date: boolean
}

export interface ReasonRevalidation extends RuleEvaluationFields {
  reason_key: string
  description?: string
  comparison?: ComparisonOp
  threshold?: number
  kind?: ReasonKind
  snapshot?: { status: ReasonStatus | null; value: number | null }
  timeline?: RevalidationPoint[]
  now?: RevalidationPoint
  delta?: { now: RevalidationSource[]; at_purchase: RevalidationSource[] } | null
  monitor?: {
    comparison: ComparisonOp
    threshold: number
    kind: ReasonKind
    estimated_next_filing?: string
    last_period_end?: string
    next_base?: RevalidationSource
    required_value?: number
  }
  error?: string
}

export interface PositionRevalidation {
  ticker: string
  purchase_date: string
  reasons: ReasonRevalidation[]
}

export interface PositionReason {
  current_rule_status?: RuleEvaluationFields['rule_status']
  current_evidence_status?: RuleEvaluationFields['evidence_status']
  current_value_unit?: string
  current_comparison_value?: number | null
  id: number
  reason_key: string
  reason_snapshot: ReasonSnapshot | null
  // Filled by GET /portfolio/summary.
  current_status?: ReasonStatus
  current_computed_value?: number | null
  current_as_of?: string | null
}

export interface CreatePositionPayload {
  ticker: string
  quantity: number
  purchase_price: number
  purchase_date: string
  reason_keys?: string[]
  thesis?: string
}

// "Attack the Thesis" -- an adversarial review of a position's Decision
// Journal entry (agent.run_thesis_attack), gated by the same Evidence Gate
// discipline as InvestigationReport.
export interface ThesisReview {
  id: number
  purchase_id: number
  ticker: string
  reason_key: string
  thesis: string
  thesis_status: "Still Holds" | "Weakened" | "Broken" | null
  counter_evidence: string | null
  supporting_evidence: string | null
  confidence: "high" | "medium" | "low" | null
  human_review_recommended: boolean | null
  rationale: string | null
  escalated: boolean
  escalation_reason: string | null
  trace_json: string[] | null
  created_at: string
}

// One side's output from Mr. Bull / Mr. Bear Cross-Debate
// (agent.run_bull_bear_debate) -- either a grounded case, or an
// escalation if that side couldn't build one.
export interface DebateCase {
  side: "bull" | "bear"
  escalated: boolean
  escalation_reason?: string
  key_points?: string[]
  strongest_evidence?: string
  confidence?: "high" | "medium" | "low"
}

export interface ThesisDebate {
  id: number
  purchase_id: number
  ticker: string
  reason_key: string
  thesis: string
  bull_case: DebateCase | null
  bear_case: DebateCase | null
  bull_rebuttal: string | null
  bear_rebuttal: string | null
  trace_json: string[] | null
  created_at: string
}

export interface PortfolioPosition extends Position {
  still_true: boolean | null
  current_status?: ReasonStatus
  current_computed_value?: number | null
  current_as_of?: string | null
  // Live price-based fields (market_data.py) -- display/P&L only, never
  // evidence for a reason's status. null when the quote source is down.
  current_price: number | null
  unrealized_pnl: number | null
  unrealized_pnl_pct: number | null
}

export type PortfolioCompanySummary =
  | { ticker: string; company_name: string; positions: PortfolioPosition[]; error?: undefined }
  | { ticker: string; error: string; company_name?: undefined; positions?: undefined }

// Real-time-ish price snapshot (market_data.get_quote) -- refreshed on a
// short server-side cache TTL (~30s), polled from the frontend at a
// similar cadence rather than streamed.
export interface Quote {
  source?: string
  price_type?: string
  as_of?: string
  ticker: string
  price: number
  previous_close: number | null
  change: number | null
  change_pct: number | null
  day_high: number | null
  day_low: number | null
  volume: number | null
  fifty_two_week_high: number | null
  fifty_two_week_low: number | null
  currency: string | null
  market_time: number | null
  cached_at: number
}

export interface PricePoint {
  date: string
  close: number
}

export type HistoryRange = "1d" | "5d" | "1mo" | "3mo" | "6mo" | "1y" | "5y" | "max"

export interface ApiErrorBody {
  detail?: string | { msg: string }[]
  message?: string
}

export interface NaturalClaim {
 claim_id:string;expectation:string;checkable_question:string;evidence_queries:string[];ambiguities:string[];limitations:string[];user_clarification?:string
}
export interface NaturalObservation {
 claim_id:string;statement:string;quote:string;role:string;fact_or_inference:string;
 source:{source_url:string;form:string;period_end:string;filed:string;accession:string}
}
export interface NaturalInvestigation {
 evaluation_date:string;period_start:string;period_end:string;evidence_status:string;
 claims:{claim_id:string;evidence_status:string;supporting_evidence:NaturalObservation[];contradicting_evidence:NaturalObservation[]}[];
 what_we_know:NaturalObservation[];
 what_is_uncertain:{claim_id:string;status?:string;question?:string;ambiguity?:string}[];
 what_to_investigate_next:{claim_id:string;question:string;search_topics:string[];follow_up_questions?:string[]}[];
 limitations:string[];usage:{input_tokens:number;output_tokens:number}
}
