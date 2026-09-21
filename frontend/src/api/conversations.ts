import { apiClient } from "@/api/client"
import type { ChatConversationDetail, ChatConversationSummary, SendMessageResponse } from "@/types"

export async function fetchConversations(): Promise<ChatConversationSummary[]> {
  const { data } = await apiClient.get<ChatConversationSummary[]>("/conversations")
  return data
}

export async function fetchConversation(id: number): Promise<ChatConversationDetail> {
  const { data } = await apiClient.get<ChatConversationDetail>(`/conversations/${id}`)
  return data
}

export async function deleteConversation(id: number): Promise<void> {
  await apiClient.delete(`/conversations/${id}`)
}

// Costs real money (LLM call). Only ever invoke from an explicit,
// user-confirmed action -- never automatically or on mount. Persists both
// sides of the exchange server-side; pass conversationId=null to start a
// new conversation (the backend derives its title from this question).
export async function sendMessage(
  question: string,
  conversationId: number | null,
): Promise<SendMessageResponse> {
  const { data } = await apiClient.post<SendMessageResponse>("/conversations/messages", {
    question,
    conversation_id: conversationId,
  })
  return data
}
