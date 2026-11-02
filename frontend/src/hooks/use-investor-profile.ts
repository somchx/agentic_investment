import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { fetchInvestorProfileSettings, updateInvestorProfileSettings } from "@/api/investor-profile"
import { queryKeys } from "@/hooks/query-keys"
import type { UpdateInvestorProfileSettingsPayload } from "@/types"

export function useInvestorProfileSettings() {
  return useQuery({
    queryKey: queryKeys.investorProfile,
    queryFn: fetchInvestorProfileSettings,
  })
}

export function useUpdateInvestorProfileSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: UpdateInvestorProfileSettingsPayload) => updateInvestorProfileSettings(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.investorProfile })
    },
  })
}
