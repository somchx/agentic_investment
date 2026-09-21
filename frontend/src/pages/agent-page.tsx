import { useEffect, useRef, useState, type KeyboardEvent, type MouseEvent } from "react"
import { Folder, Menu, MessageSquarePlus, Send, Trash2, X } from "lucide-react"
import { CostConfirmDialog } from "@/components/cost-confirm-dialog"
import { ChatMessage, type DisplayMessage } from "@/components/agent/chat-message"
import { AgentEmptyState } from "@/components/agent/agent-empty-state"
import { Select } from "@/components/ui/select"
import { useConversation, useConversations, useDeleteConversation, useSendMessage } from "@/hooks/use-conversations"
import { useCompanies } from "@/hooks/use-companies"
import { getApiErrorMessage } from "@/api/client"
import { useTranslation } from "@/i18n/context"
import { cn } from "@/lib/utils"
import type { ChatTurn } from "@/types"

// Sentinel for the scope picker's "My Portfolio" option -- the backend
// only has one chat endpoint (portfolio-wide), so picking a single ticker
// here doesn't change which endpoint is called, it just prefixes the
// question with which company to focus on (see buildScopedQuestion below).
// The agent can still look at any ticker on its own even in portfolio
// scope; this is a hint for the common case of "I mean THIS one."
const PORTFOLIO_SCOPE = "__portfolio__"

function buildScopedQuestion(scope: string, question: string): string {
  return scope === PORTFOLIO_SCOPE ? question : `Regarding ${scope}: ${question}`
}

// This page always asks across the whole portfolio -- no forced company
// picker before you can type (the scope selector below is an optional
// hint, not a gate). Every conversation is persisted server-side
// (chat_conversations / chat_messages) as it happens, same reasoning as
// InvestigationRun: each message is a paid LLM call, so a conversation is
// a permanent record, not disposable client state. "New chat" never
// deletes the old thread -- it's already saved -- it just starts a fresh
// one, reachable again from the history list.
export function AgentPage() {
  const { t } = useTranslation()
  const [historyOpen, setHistoryOpen] = useState(false)
  const [scope, setScope] = useState(PORTFOLIO_SCOPE)
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [input, setInput] = useState("")
  const [error, setError] = useState<string | null>(null)
  // Armed once the user has confirmed the paid-conversation dialog for the
  // CURRENT conversation. Reset on "New chat" so a fresh conversation asks again.
  const [armed, setArmed] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const { data: companies } = useCompanies()
  const { data: conversations } = useConversations()
  const { data: activeConversation } = useConversation(activeId)
  const sendMessage = useSendMessage()
  const deleteConversation = useDeleteConversation()

  // Load a past conversation's messages once fetched.
  useEffect(() => {
    if (!activeConversation) return
    setMessages(
      activeConversation.messages.map((m) => ({
        role: m.role,
        content: m.content,
        costUsd: m.cost_usd ?? undefined,
        toolCalls: m.tool_calls_json ?? undefined,
      })),
    )
    setArmed(true) // a saved conversation already has at least one paid turn
  }, [activeConversation])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages])

  // Auto-grow the input as the user types, capped at ~6 lines with scroll
  // beyond that -- matches the reference input box wrapping to new lines
  // instead of staying a fixed single-line field.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, 144)}px`
  }, [input])

  function handleInputKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      trySend(input)
    }
  }

  function startNewChat() {
    setActiveId(null)
    setMessages([])
    setArmed(false)
    setError(null)
    setInput("")
    setScope(PORTFOLIO_SCOPE)
    setHistoryOpen(false)
  }

  function openConversation(id: number) {
    if (id === activeId) {
      setHistoryOpen(false)
      return
    }
    setActiveId(id)
    setError(null)
    setInput("")
    setHistoryOpen(false)
  }

  function handleDelete(id: number, e: MouseEvent) {
    e.stopPropagation()
    deleteConversation.mutate(id)
    if (id === activeId) startNewChat()
  }

  function trySend(question: string) {
    const trimmed = question.trim()
    if (!trimmed || sendMessage.isPending) return
    trySendExact(buildScopedQuestion(scope, trimmed))
  }

  // Used by regenerate, which resends a *previous* message's exact text
  // (already scoped when it was first sent) rather than re-scoping it
  // against whatever the scope picker happens to be set to right now.
  function trySendExact(finalQuestion: string) {
    if (sendMessage.isPending) return
    if (!armed) {
      setPendingQuestion(finalQuestion)
      setConfirmOpen(true)
      return
    }
    void doSend(finalQuestion)
  }

  async function doSend(question: string) {
    setError(null)
    setInput("")
    const history: ChatTurn[] = messages.map(({ role, content }) => ({ role, content }))
    setMessages((prev) => [...prev, { role: "user", content: question }])
    try {
      const res = await sendMessage.mutateAsync({ question, conversationId: activeId })
      setActiveId(res.conversation_id)
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, costUsd: res.cost_usd, toolCalls: res.tool_calls },
      ])
    } catch (err) {
      setError(getApiErrorMessage(err, t("ask_agent_err_default")))
      setMessages((prev) => prev.slice(0, -1))
    }
  }

  function handleConfirm() {
    setArmed(true)
    setConfirmOpen(false)
    if (pendingQuestion) {
      void doSend(pendingQuestion)
      setPendingQuestion(null)
    }
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem-3rem)] gap-3 md:h-[calc(100vh-3.5rem-4rem)]">
      {/* Chat-history panel -- toggled by the hamburger button, independent
          of the app's own nav sidebar. Overlays on narrow screens, sits
          inline (pushing the chat column over) on wider ones. */}
      {historyOpen && (
        <div className="fixed inset-0 z-30 md:hidden" onClick={() => setHistoryOpen(false)}>
          <div className="absolute inset-0 bg-black/50" />
        </div>
      )}
      <aside
        className={cn(
          "flex-none flex-col overflow-hidden rounded-lg border border-[var(--border-primary)] bg-[var(--bg-sidebar)] transition-[width]",
          historyOpen ? "fixed inset-y-2 left-2 z-30 flex w-64 md:relative md:inset-auto md:left-auto" : "hidden w-0",
        )}
      >
        <div className="flex flex-none items-center justify-between border-b border-[var(--border-secondary)] px-3 py-2.5">
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-ghost)]">
            {t("chat_history_title")}
          </span>
          <button
            type="button"
            onClick={() => setHistoryOpen(false)}
            aria-label={t("sidebar_close")}
            className="rounded p-1 text-[var(--text-faint)] hover:bg-[var(--bg-hover)] md:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <button
          type="button"
          onClick={startNewChat}
          className="mx-2 mt-2 flex flex-none items-center gap-2 rounded-full px-2.5 py-2 text-[13px] text-[var(--text-faint)] transition-colors hover:bg-[var(--bg-card)] hover:text-[var(--text-primary)]"
        >
          <MessageSquarePlus className="h-4 w-4 flex-none" />
          {t("agent_new_chat")}
        </button>
        <div className="flex-1 overflow-y-auto p-2">
          {conversations && conversations.length > 0 ? (
            conversations.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => openConversation(c.id)}
                className={cn(
                  "group flex w-full items-center justify-between gap-2 rounded-full px-2.5 py-2 text-left text-[13px] transition-colors",
                  c.id === activeId
                    ? "bg-[var(--bg-card)] text-[var(--text-primary)]"
                    : "text-[var(--text-faint)] hover:bg-[var(--bg-card)] hover:text-[var(--text-primary)]",
                )}
              >
                <span className="truncate">{c.title}</span>
                <span
                  role="button"
                  onClick={(e) => handleDelete(c.id, e)}
                  aria-label={t("chat_history_delete_aria")}
                  className="flex-none rounded p-1 text-[var(--text-ghost)] opacity-0 transition-opacity hover:text-[var(--accent-red)] group-hover:opacity-100"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </span>
              </button>
            ))
          ) : (
            <p className="px-2.5 py-2 text-xs text-[var(--text-ghost)]">{t("chat_history_empty")}</p>
          )}
        </div>
      </aside>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* Bare hamburger only -- no title bar, matching the reference
            chat UI's minimal top. "New chat" lives in the history panel. */}
        <div className="flex flex-none items-center px-1 py-2">
          <button
            type="button"
            onClick={() => setHistoryOpen((v) => !v)}
            aria-label={t("chat_history_toggle_aria")}
            className="flex h-9 w-9 flex-none items-center justify-center rounded-md text-[var(--text-faint)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 sm:px-5">
          {messages.length === 0 ? (
            <AgentEmptyState ticker={scope === PORTFOLIO_SCOPE ? null : scope} onPick={trySend} />
          ) : (
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
              {messages.map((m, i) => (
                <ChatMessage
                  key={i}
                  message={m}
                  onEdit={m.role === "user" ? () => setInput(m.content) : undefined}
                  onRegenerate={
                    m.role === "assistant" && i > 0 ? () => trySendExact(messages[i - 1].content) : undefined
                  }
                />
              ))}
              {sendMessage.isPending && <p className="px-1 text-xs text-[var(--text-ghost)]">{t("agent_thinking")}</p>}
            </div>
          )}
        </div>

        {error && <p className="mx-auto w-full max-w-3xl flex-none px-4 pb-1 text-sm text-destructive">{error}</p>}

        {/* Input pill: two stacked rows inside one rounded container, like
            the reference -- text row on top, controls row below. */}
        <div className="mx-auto w-full max-w-3xl flex-none px-3 pb-3 sm:px-5">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              trySend(input)
            }}
            className="flex flex-col gap-1 rounded-3xl border border-[var(--border-primary)] bg-[var(--bg-card)] px-4 py-2.5 shadow-sm focus-within:border-[var(--accent-blue)]"
          >
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder={t("agent_portfolio_input_placeholder")}
              className="max-h-36 w-full resize-none overflow-y-auto bg-transparent py-1 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-ghost)] focus-visible:shadow-none focus-visible:outline-none"
              disabled={sendMessage.isPending}
            />
            <div className="flex items-center justify-between gap-2">
              <Select
                value={scope}
                onChange={setScope}
                align="left"
                // This trigger sits at the very bottom of the page (right
                // above the input), so a panel opening downward would run
                // off the viewport -- open upward instead.
                panelClassName="absolute left-0 bottom-full z-50 mb-1 min-w-full w-max max-w-[min(90vw,20rem)] max-h-72 overflow-y-auto rounded-lg border border-[var(--border-primary)] bg-[var(--bg-card)] py-1 shadow-xl"
                className="flex items-center gap-1.5 rounded-full bg-[var(--badge-bg)] px-3 py-1.5 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                options={[
                  {
                    value: PORTFOLIO_SCOPE,
                    label: (
                      <span className="inline-flex items-center gap-1.5">
                        <Folder className="h-3.5 w-3.5" />
                        {t("agent_portfolio_option_label")}
                      </span>
                    ),
                  },
                  ...(companies ?? []).map((c) => ({ value: c.ticker, label: `${c.ticker} — ${c.name}` })),
                ]}
              />
              <button
                type="submit"
                aria-label={t("agent_send_aria")}
                disabled={!input.trim() || sendMessage.isPending}
                className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-[var(--accent-blue)] text-[var(--bg-primary)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            </div>
          </form>
        </div>
      </div>

      <CostConfirmDialog
        open={confirmOpen}
        onOpenChange={(open) => {
          setConfirmOpen(open)
          if (!open) setPendingQuestion(null)
        }}
        title={t("agent_dialog_title")}
        description={t("agent_portfolio_dialog_description")}
        onConfirm={handleConfirm}
        isPending={sendMessage.isPending}
        confirmLabel={t("agent_dialog_confirm")}
      />
    </div>
  )
}
