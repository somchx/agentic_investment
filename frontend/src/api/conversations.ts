import { API_BASE_URL, apiClient } from "@/api/client"
import { getToken } from "@/lib/auth-storage"
import type { AgentProgressEvent, AgentTraceDetail, ChatConversationDetail, ChatConversationSummary, SendMessageResponse } from "@/types"

export async function fetchConversations(): Promise<ChatConversationSummary[]> {
  const { data } = await apiClient.get<ChatConversationSummary[]>("/conversations")
  return data
}

export async function fetchConversation(id: number): Promise<ChatConversationDetail> {
  const { data } = await apiClient.get<ChatConversationDetail>(`/conversations/${id}`)
  return data
}

// Free, read-only: the stored investigation trace behind one answer.
export async function fetchTrace(traceId: number): Promise<AgentTraceDetail> {
  const { data } = await apiClient.get<AgentTraceDetail>(`/conversations/traces/${traceId}`)
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

// Same paid call as sendMessage, but reads the Server-Sent Events stream so
// the UI can show what the agent is doing while it works. Resolves with the
// final response; rejects with the server's error detail.
export async function sendMessageStream(
  question: string,
  conversationId: number | null,
  onEvent: (event: AgentProgressEvent) => void,
): Promise<SendMessageResponse> {
  const token = getToken()
  const res = await fetch(`${API_BASE_URL}/api/conversations/messages/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept-Language": window.localStorage.getItem("lang") === "th" ? "th" : "en",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ question, conversation_id: conversationId }),
  })
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => null)
    throw new Error(typeof body?.detail === "string" ? body.detail : `Request failed (${res.status})`)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep: number
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      const line = chunk.split("\n").find((l) => l.startsWith("data: "))
      if (!line) continue
      const event = JSON.parse(line.slice(6)) as AgentProgressEvent
      onEvent(event)
      if (event.type === "done" && event.response) return event.response
      if (event.type === "error") throw new Error(event.detail || "The agent failed")
    }
  }
  throw new Error("The connection closed before the agent finished")
}
