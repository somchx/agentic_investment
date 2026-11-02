import type { ComponentType, ReactNode } from "react"

interface PageHeaderProps {
  icon: ComponentType<{ className?: string }>
  title: string
  subtitle?: string
  actions?: ReactNode
}

/** Page-level title block -- icon chip + title + subtitle, same treatment
 * on every routed page, matching the reference project's PageHeader. */
export function PageHeader({ icon: Icon, title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h2>
          {subtitle && <p className="text-sm text-[var(--text-muted)]">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
