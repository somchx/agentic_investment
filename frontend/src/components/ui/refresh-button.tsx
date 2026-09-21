import { RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"

export function RefreshButton({
  onClick,
  pending,
  label,
}: {
  onClick: () => void
  pending?: boolean
  label?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending}
      className="flex items-center gap-1.5 rounded-md border border-[var(--border-primary)] bg-[var(--badge-bg)] px-3 py-1.5 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:opacity-50"
    >
      <RefreshCw className={cn("h-3.5 w-3.5", pending && "animate-spin")} />
      {label}
    </button>
  )
}
