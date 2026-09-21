import { Sparkles } from "lucide-react"
import { useTranslation } from "@/i18n/context"

const TICKER_SUGGESTION_KEYS = ["agent_suggestion_1", "agent_suggestion_2", "agent_suggestion_3", "agent_suggestion_4"] as const
const PORTFOLIO_SUGGESTION_KEYS = [
  "agent_portfolio_suggestion_1",
  "agent_portfolio_suggestion_2",
  "agent_portfolio_suggestion_3",
  "agent_portfolio_suggestion_4",
] as const

export function AgentEmptyState({
  ticker,
  onPick,
}: {
  // null = portfolio-wide scope (not one company)
  ticker: string | null
  onPick: (question: string) => void
}) {
  const { t } = useTranslation()
  const vars: Record<string, string> = ticker ? { ticker } : {}
  const headingKey = ticker ? "agent_empty_heading" : "agent_portfolio_empty_heading"
  const subtitleKey = ticker ? "agent_empty_subtitle" : "agent_portfolio_empty_subtitle"
  const suggestionKeys = ticker ? TICKER_SUGGESTION_KEYS : PORTFOLIO_SUGGESTION_KEYS

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-4 py-10 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--accent-purple)]/15">
        <Sparkles className="h-6 w-6 text-[var(--accent-purple)]" />
      </div>
      <div className="flex flex-col gap-1.5">
        <h2 className="text-base font-bold text-[var(--text-primary)]">{t(headingKey, vars)}</h2>
        <p className="max-w-md text-sm text-[var(--text-muted)]">{t(subtitleKey, vars)}</p>
      </div>
      <div className="flex max-w-lg flex-wrap items-center justify-center gap-2">
        {suggestionKeys.map((key) => {
          const question = t(key, vars)
          return (
            <button
              key={key}
              type="button"
              onClick={() => onPick(question)}
              className="rounded-full border border-[var(--border-primary)] bg-[var(--bg-card)] px-3.5 py-1.5 text-xs text-[var(--text-faint)] transition-colors hover:border-[var(--accent-purple)]/50 hover:text-[var(--text-primary)]"
            >
              {question}
            </button>
          )
        })}
      </div>
    </div>
  )
}
