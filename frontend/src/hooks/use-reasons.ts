import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createReason, deleteReason, fetchReasons, fetchXbrlTags } from "@/api/reasons"
import { queryKeys } from "@/hooks/query-keys"
import type { CreateReasonPayload } from "@/types"

export function useReasons(ticker?: string) {
  return useQuery({
    queryKey: queryKeys.reasons(ticker),
    queryFn: () => fetchReasons(ticker),
  })
}

export function useXbrlTags(ticker: string) {
  return useQuery({
    queryKey: queryKeys.xbrlTags(ticker),
    queryFn: () => fetchXbrlTags(ticker),
    enabled: Boolean(ticker),
  })
}

export function useCreateReason() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateReasonPayload) => createReason(payload),
    // The response is a preview evaluation, not a Reason row -- it has no
    // `ticker` field. Use the mutation's own input (`variables`) instead,
    // which always has the ticker the reason was created for.
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.reasons(variables.ticker) })
      queryClient.invalidateQueries({ queryKey: queryKeys.reasons() })
      queryClient.invalidateQueries({ queryKey: queryKeys.report(variables.ticker) })
    },
  })
}

export function useDeleteReason() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (reasonKey: string) => deleteReason(reasonKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reasons"] })
      queryClient.invalidateQueries({ queryKey: ["report"] })
    },
  })
}
