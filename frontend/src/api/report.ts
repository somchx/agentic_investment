import { apiClient } from "@/api/client"
import type { AskAgentResponse, ChatTurn, CompanyReport, PersonalizeResponse } from "@/types"

export async function fetchReport(ticker: string): Promise<CompanyReport> {
  const { data } = await apiClient.get<CompanyReport>(`/report/${encodeURIComponent(ticker)}`)
  return data
}

// Costs real money (LLM call). Only ever invoke from an explicit,
// user-confirmed action -- never automatically or on mount. `history` is
// this chat session's prior turns (not stored server-side) so a follow-up
// question has context.
export async function askAgent(
  ticker: string,
  question: string,
  history: ChatTurn[] = [],
): Promise<AskAgentResponse> {
  const { data } = await apiClient.post<AskAgentResponse>(
    `/ask-agent/${encodeURIComponent(ticker)}`,
    { question, history },
  )
  return data
}

// Portfolio-wide version of askAgent -- not scoped to one company, for
// "how's my portfolio doing" style questions. Same cost/confirm rules.
export async function askAgentPortfolio(
  question: string,
  history: ChatTurn[] = [],
): Promise<AskAgentResponse> {
  const { data } = await apiClient.post<AskAgentResponse>("/ask-agent", { question, history })
  return data
}

// Also costs real money (LLM call). Same confirm-before-send treatment as askAgent.
export async function personalize(ticker: string, profileId: string): Promise<PersonalizeResponse> {
  const { data } = await apiClient.post<PersonalizeResponse>(
    `/personalize/${encodeURIComponent(ticker)}`,
    { profile_id: profileId },
  )
  return data
}
