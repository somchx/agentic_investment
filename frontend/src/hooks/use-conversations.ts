import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { deleteConversation, fetchConversation, fetchConversations, sendMessage } from "@/api/conversations"
import { queryKeys } from "@/hooks/query-keys"

export function useConversations() {
  return useQuery({
    queryKey: queryKeys.conversations,
    queryFn: fetchConversations,
  })
}

export function useConversation(id: number | null) {
  return useQuery({
    queryKey: queryKeys.conversation(id ?? -1),
    queryFn: () => fetchConversation(id as number),
    enabled: id !== null,
  })
}

export function useSendMessage() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ question, conversationId }: { question: string; conversationId: number | null }) =>
      sendMessage(question, conversationId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.conversations })
      queryClient.invalidateQueries({ queryKey: queryKeys.conversation(data.conversation_id) })
    },
  })
}

export function useDeleteConversation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteConversation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.conversations })
    },
  })
}
