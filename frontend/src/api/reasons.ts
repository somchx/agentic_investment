import { apiClient } from "@/api/client"
import type { CreateReasonPayload, CreateReasonResult, Reason, XbrlTag } from "@/types"

export async function fetchReasons(ticker?: string): Promise<Reason[]> {
  const { data } = await apiClient.get<Reason[]>("/reasons", {
    params: ticker ? { ticker } : undefined,
  })
  return data
}

export async function createReason(payload: CreateReasonPayload): Promise<CreateReasonResult> {
  const { data } = await apiClient.post<CreateReasonResult>("/reasons", payload)
  return data
}

export async function deleteReason(reasonKey: string): Promise<void> {
  await apiClient.delete(`/reasons/${encodeURIComponent(reasonKey)}`)
}

export async function fetchXbrlTags(ticker: string): Promise<XbrlTag[]> {
  const { data } = await apiClient.get<XbrlTag[]>(`/xbrl-tags/${encodeURIComponent(ticker)}`)
  return data
}
