import { apiClient } from "@/api/client"
import type { ScreenResult } from "@/types"

export async function runScreen(reasonKeys: string[]): Promise<ScreenResult> {
  const params = new URLSearchParams()
  reasonKeys.forEach((k) => params.append("reason_key", k))
  const { data } = await apiClient.get<ScreenResult>("/screen", { params })
  return data
}
