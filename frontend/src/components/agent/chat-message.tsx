import { useState } from "react"
import { Check, Copy, Pencil, RotateCcw } from "lucide-react"
import { cn } from "@/lib/utils"
import { useTranslation } from "@/i18n/context"
import type { ChatTurn, ToolCall } from "@/types"

export interface DisplayMessage extends ChatTurn {
  costUsd?: number
  toolCalls?: ToolCall[]
}

function CopyButton({ text }: { text: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard unavailable (e.g. insecure context) -- silently ignore
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={t("chat_copy_aria")}
      className="flex items-center gap-1 rounded p-1 text-[var(--text-ghost)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}

export function ChatMessage({
  message,
  onEdit,
  onRegenerate,
}: {
  message: DisplayMessage
  // Puts this question back in the input box to modify and resend --
  // real functionality, not a decorative icon.
  onEdit?: () => void
  // Re-asks the question that produced this answer -- real functionality
  // (a fresh, separately-billed call), not a decorative icon.
  onRegenerate?: () => void
}) {
  const { t } = useTranslation()
  const isUser = message.role === "user"

  if (isUser) {
    return (
      <div className="flex w-full flex-col items-end gap-1">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-3xl bg-[var(--accent-blue)]/15 px-4 py-2.5 text-sm leading-relaxed text-[var(--text-primary)] sm:max-w-[70%]">
          {message.content}
        </div>
        <div className="flex items-center gap-1">
          <CopyButton text={message.content} />
          {onEdit && (
            <button
              type="button"
              onClick={onEdit}
              aria-label={t("chat_edit_aria")}
              className="flex items-center gap-1 rounded p-1 text-[var(--text-ghost)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
    )
  }

  // Assistant messages render as plain text (no bubble/border), matching
  // the reference chat UI -- only the user's own turns get a bubble.
  return (
    <div className="flex w-full flex-col gap-1.5">
      <div className="whitespace-pre-wrap break-words text-sm leading-relaxed text-[var(--text-primary)]">
        {message.content}
      </div>

      <div className="flex items-center gap-1">
        <CopyButton text={message.content} />
        {onRegenerate && (
          <button
            type="button"
            onClick={onRegenerate}
            aria-label={t("chat_regenerate_aria")}
            className="flex items-center gap-1 rounded p-1 text-[var(--text-ghost)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        )}

        {message.costUsd !== undefined && (
          <p className={cn("ml-1 font-mono-num text-[11px] text-[var(--text-ghost)]")}>
            {t("ask_agent_cost", { cost: message.costUsd.toFixed(4) })} ·{" "}
            {t(message.toolCalls?.length === 1 ? "ask_agent_tool_calls" : "ask_agent_tool_calls_plural", {
              count: message.toolCalls?.length ?? 0,
            })}
            {message.toolCalls && message.toolCalls.length > 0 && (
              <>
                {" · "}
                {t("agent_tool_calls_detail", { tools: message.toolCalls.map((tc) => tc.name).join(", ") })}
              </>
            )}
          </p>
        )}
      </div>
    </div>
  )
}
