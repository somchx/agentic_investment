import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createPosition,
  deletePosition,
  fetchPortfolioSummary,
  fetchPositions,
} from "@/api/positions"
import { queryKeys } from "@/hooks/query-keys"
import type { CreatePositionPayload } from "@/types"

export function usePositions() {
  return useQuery({
    queryKey: queryKeys.positions,
    queryFn: fetchPositions,
  })
}

export function usePortfolioSummary() {
  return useQuery({
    queryKey: queryKeys.portfolioSummary,
    queryFn: fetchPortfolioSummary,
  })
}

export function useCreatePosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreatePositionPayload) => createPosition(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.positions })
      queryClient.invalidateQueries({ queryKey: queryKeys.portfolioSummary })
    },
  })
}

export function useDeletePosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deletePosition(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.positions })
      queryClient.invalidateQueries({ queryKey: queryKeys.portfolioSummary })
    },
  })
}
