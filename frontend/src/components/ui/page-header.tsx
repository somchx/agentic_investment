import type { ComponentType, ReactNode, CSSProperties } from "react"

interface PageHeaderProps {
  icon: ComponentType<{ className?: string; style?: CSSProperties }>
  title: ReactNode
  /** Short description under the title -- optional, but keep the wording present when the page benefits from context. */
  subtitle?: ReactNode
  /** Small badge next to the title, e.g. a status or record count. */
  badge?: ReactNode
  /** Right-aligned controls -- buttons, filters, refresh, etc. */
  actions?: ReactNode
  iconColor?: string
  /** Extra classes merged onto the icon, e.g. `animate-pulse`. */
  iconClassName?: string
}

/**
 * Canonical page header -- icon, title, optional subtitle/badge, and a
 * right-aligned actions slot. Every page should render this once at the
 * top instead of a bespoke `<h1>`, so the app reads as one consistent
 * product -- matches the reference design system's PageHeader exactly.
 */
export function PageHeader({
  icon: Icon,
  title,
  subtitle,
  badge,
  actions,
  iconColor = "#f0883e",
  iconClassName = "",
}: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-center gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-[var(--border-primary)] bg-[var(--bg-card)]">
          <Icon className={`h-5 w-5 ${iconClassName}`} style={{ color: iconColor }} />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-bold text-[var(--text-primary)]">{title}</h1>
            {badge}
          </div>
          {subtitle && <p className="mt-0.5 text-sm text-[var(--text-muted)]">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
