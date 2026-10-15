import { apiClient } from "@/api/client"
import type { InvestorProfileSettings, UpdateInvestorProfileSettingsPayload } from "@/types"

export async function fetchInvestorProfileSettings(): Promise<InvestorProfileSettings | null> {
  const { data } = await apiClient.get<InvestorProfileSettings | null>("/investor-profile")
  return data
}

export async function updateInvestorProfileSettings(
  payload: UpdateInvestorProfileSettingsPayload,
): Promise<InvestorProfileSettings> {
  const { data } = await apiClient.put<InvestorProfileSettings>("/investor-profile", payload)
  return data
}
