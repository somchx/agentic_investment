import { Sparkles } from "lucide-react"
import { useTranslation } from "@/i18n/context"

/** Chat "thinking" indicator -- the same pulsing sparkle and bouncing dots as
 * the AI Summary's thinking state, sized for a chat turn. */
export function AgentThinking() {
  const { t } = useTranslation()
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 py-1">
      <div className="relative grid h-8 w-8 flex-none place-items-center">
        <span className="absolute inset-0 animate-ping rounded-full bg-primary/20" />
        <span className="relative grid h-8 w-8 place-items-center rounded-full brand-gradient text-white shadow-glow">
          <Sparkles className="h-4 w-4 animate-pulse" />
        </span>
      </div>
      <div className="flex flex-col gap-0.5">
        <p className="flex items-center gap-1 text-sm font-semibold text-[var(--text-primary)]">
          {t("agent_thinking")}
          <span className="inline-flex gap-0.5" aria-hidden="true">
            {[0, 150, 300].map((delay) => (
              <span key={delay} className="h-1 w-1 animate-bounce rounded-full bg-primary" style={{ animationDelay: `${delay}ms` }} />
            ))}
          </span>
        </p>
        <p className="text-xs text-[var(--text-muted)]">{t("agent_thinking_hint")}</p>
      </div>
    </div>
  )
}
