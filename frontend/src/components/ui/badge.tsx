import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-[var(--border-primary)] bg-[var(--badge-bg)] text-[var(--text-muted)]",
        outline: "border-border text-foreground",
        supported: "border-status-supported/30 bg-status-supported/15 text-status-supported",
        weakened: "border-status-weakened/30 bg-status-weakened/15 text-status-weakened",
        broken: "border-status-broken/30 bg-status-broken/15 text-status-broken",
        unknown: "border-[var(--border-primary)] bg-[var(--badge-bg)] text-[var(--text-muted)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
