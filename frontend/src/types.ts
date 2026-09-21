// Shared TypeScript interfaces mirroring the FastAPI backend contract
// (see project README / task spec for the authoritative REST contract).

export interface User {
  id: string
  email: string
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

export interface Reason {
  reason_key: string
  ticker: string
  metric: string
  comparison: ComparisonOp
  threshold: number
  kind: ReasonKind
  denominator_metric?: string | null
  description: string
  instant: boolean
  is_builtin: boolean
}

export interface CreateReasonPayload {
  reason_key: string
  ticker: string
  metric: string
  comparison: ComparisonOp
  threshold: number
  kind: ReasonKind
  denominator_metric: string
  description: string
  instant: boolean
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
}

export interface XbrlTag {
  tag: string
  label: string
  quarterly: boolean
  instant: boolean
}

export type ReasonStatus = "Supported" | "Weakened" | "Broken" | "Not enough data"

export interface ReportReason {
  reason_key: string
  description: string
  status: ReasonStatus
  computed_value: number | null
  as_of: string | null
  previous_status: ReasonStatus | null
  [key: string]: unknown
}

export interface CompanyReport {
  ticker: string
  company_name: string
  reasons: ReportReason[]
  history: unknown[]
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
  created_at: string
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
  tool_calls: ToolCall[]
  cost_usd: number
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

export interface PersonalizeResponse {
  ticker: string
  priority: string | number
  rationale?: string
  cost_usd: number
  [key: string]: unknown
}

export interface ScreenReasonResult {
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

export interface ReasonSnapshot {
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
  reason_key: string | null
  reason_snapshot: ReasonSnapshot | null
}

export interface CreatePositionPayload {
  ticker: string
  quantity: number
  purchase_price: number
  purchase_date: string
  reason_key?: string
}

export interface PortfolioPosition extends Position {
  still_true: boolean | null
  current_status?: ReasonStatus
  current_computed_value?: number | null
  current_as_of?: string | null
}

export interface PortfolioCompanySummary {
  ticker: string
  company_name: string
  positions: PortfolioPosition[]
}

export interface ApiErrorBody {
  detail?: string | { msg: string }[]
  message?: string
}
