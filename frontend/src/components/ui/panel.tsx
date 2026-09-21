import type { ReactNode } from "react"

export function Panel({
  title,
  description,
  color = "#58a6ff",
  action,
  children,
  className,
}: {
  title?: ReactNode
  description?: ReactNode
  color?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <div className={className ?? "bg-[var(--bg-card)] border border-[var(--border-primary)] rounded-lg p-4"}>
      {title && (
        <div className="flex items-start justify-between gap-3 mb-3 pb-2 border-b border-[var(--border-primary)]">
          <div className="flex items-start gap-2">
            <div className="w-1 h-4 mt-0.5 rounded-full flex-none" style={{ backgroundColor: color }} />
            <div>
              <h2 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                {title}
              </h2>
              {description && (
                <p className="mt-1 text-xs font-normal normal-case tracking-normal text-[var(--text-muted)]">
                  {description}
                </p>
              )}
            </div>
          </div>
          {action}
        </div>
      )}
      {children}
    </div>
  )
}
