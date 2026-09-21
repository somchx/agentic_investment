import { apiClient } from "@/api/client"
import type { CreatePositionPayload, PortfolioCompanySummary, Position } from "@/types"

export async function fetchPositions(): Promise<Position[]> {
  const { data } = await apiClient.get<Position[]>("/positions")
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
