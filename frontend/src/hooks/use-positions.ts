import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  attackThesis,
  createPosition,
  debateThesis,
  deletePosition,
  fetchPortfolioSummary,
  fetchPositions,
  fetchThesisDebates,
  fetchRevalidation,
  fetchThesisReviews,
} from "@/api/positions"
import { queryKeys } from "@/hooks/query-keys"
import type { CreatePositionPayload } from "@/types"

export function usePositions(ticker?: string) {
  return useQuery({
    queryKey: ticker ? ([...queryKeys.positions, ticker] as const) : queryKeys.positions,
    queryFn: () => fetchPositions(ticker),
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

export function useRevalidation(positionId: string) {
  return useQuery({
    queryKey: queryKeys.revalidation(positionId),
    queryFn: () => fetchRevalidation(positionId),
    enabled: Boolean(positionId),
  })
}

export function useThesisReviews(positionId: string) {
  return useQuery({
    queryKey: queryKeys.thesisReviews(positionId),
    queryFn: () => fetchThesisReviews(positionId),
    enabled: Boolean(positionId),
  })
}

// Money-costing mutation: never fire from a useEffect/on-mount, only from
// an explicit confirm dialog -- same rule as useInvestigate.
export function useAttackThesis(positionId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (reasonKey?: string) => attackThesis(positionId, reasonKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.thesisReviews(positionId) })
    },
  })
}

export function useThesisDebates(positionId: string) {
  return useQuery({
    queryKey: queryKeys.thesisDebates(positionId),
    queryFn: () => fetchThesisDebates(positionId),
    enabled: Boolean(positionId),
  })
}

// Money-costing mutation (roughly 2x useAttackThesis) -- same confirm-
// before-send rule.
export function useDebateThesis(positionId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (reasonKey?: string) => debateThesis(positionId, reasonKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.thesisDebates(positionId) })
    },
  })
}
