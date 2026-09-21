import type { LucideIcon } from "lucide-react"

export function EmptyState({
  icon: Icon,
  title,
  subtitle,
}: {
  icon?: LucideIcon
  title: string
  subtitle?: string
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center text-[var(--text-muted)]">
      {Icon && <Icon className="h-6 w-6 text-[var(--text-ghost)]" />}
      <p className="text-sm font-medium text-[var(--text-secondary)]">{title}</p>
      {subtitle && <p className="max-w-sm text-xs">{subtitle}</p>}
    </div>
  )
}
