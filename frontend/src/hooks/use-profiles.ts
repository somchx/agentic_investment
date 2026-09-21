import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createProfile, deleteProfile, fetchProfiles } from "@/api/profiles"
import { queryKeys } from "@/hooks/query-keys"
import type { CreateProfilePayload } from "@/types"

export function useProfiles() {
  return useQuery({
    queryKey: queryKeys.profiles,
    queryFn: fetchProfiles,
  })
}

export function useCreateProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateProfilePayload) => createProfile(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.profiles })
    },
  })
}

export function useDeleteProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteProfile(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.profiles })
    },
  })
}
