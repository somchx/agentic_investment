import { apiClient } from "@/api/client"
import type { CreatePositionPayload, PortfolioCompanySummary, Position, PositionRevalidation, ThesisDebate, ThesisReview } from "@/types"

export async function fetchPositions(ticker?: string): Promise<Position[]> {
  const { data } = await apiClient.get<Position[]>("/positions", { params: ticker ? { ticker } : undefined })
  return data
}

export async function createPosition(payload: CreatePositionPayload): Promise<Position> {
  const { data } = await apiClient.post<Position>("/positions", payload)
  return data
}

export async function deletePosition(id: string): Promise<void> {
  await apiClient.delete(`/positions/${encodeURIComponent(id)}`)
}

export async function fetchPortfolioSummary(): Promise<PortfolioCompanySummary[]> {
  const { data } = await apiClient.get<PortfolioCompanySummary[]>("/portfolio/summary")
  return data
}

// Free: point-in-time timeline, raw amounts and next-filing requirement per reason.
export async function fetchRevalidation(positionId: string): Promise<PositionRevalidation> {
  const { data } = await apiClient.get<PositionRevalidation>(`/positions/${encodeURIComponent(positionId)}/revalidation`)
  return data
}

export async function fetchThesisReviews(positionId: string): Promise<ThesisReview[]> {
  const { data } = await apiClient.get<ThesisReview[]>(
    `/positions/${encodeURIComponent(positionId)}/thesis-reviews`,
  )
  return data
}

// Costs real money (LLM call) -- only ever invoke from an explicit,
// user-confirmed action, same cost/confirm rules as investigateCompany.
// `reasonKey`: which of the purchase's reasons to challenge (default: the first).
export async function attackThesis(positionId: string, reasonKey?: string): Promise<ThesisReview> {
  const { data } = await apiClient.post<ThesisReview>(
    `/positions/${encodeURIComponent(positionId)}/attack-thesis`,
    { reason_key: reasonKey ?? null },
  )
  return data
}

export async function fetchThesisDebates(positionId: string): Promise<ThesisDebate[]> {
  const { data } = await apiClient.get<ThesisDebate[]>(
    `/positions/${encodeURIComponent(positionId)}/thesis-debates`,
  )
  return data
}

// Costs real money (LLM call, roughly 2x attackThesis -- two case-builder
// passes plus two rebuttals) -- only ever invoke from an explicit,
// user-confirmed action.
export async function debateThesis(positionId: string, reasonKey?: string): Promise<ThesisDebate> {
  const { data } = await apiClient.post<ThesisDebate>(
    `/positions/${encodeURIComponent(positionId)}/debate-thesis`,
    { reason_key: reasonKey ?? null },
  )
  return data
}
