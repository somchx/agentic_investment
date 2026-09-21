import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

// Note: border-radius is set per-variant (never in the shared base or in
// `size`) -- Tailwind emits its rounded-* utilities in a fixed scale order
// in the compiled stylesheet, so a radius class added by `size` would be
// overridden by (or override) a radius class from `variant` based on that
// fixed order, not on where it appears in the className string. Keeping
// radius a variant-only concern avoids that footgun entirely.
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // Primary CTA: the reference design system's signature orange
        // gradient + glow shadow, reserved for the one main action on a
        // form/panel (submit, send, confirm) -- not a general-purpose color.
        default: "btn-glow-gradient rounded-full text-white shadow-glow hover:shadow-glow-lg active:scale-[0.98]",
        destructive: "rounded-md bg-destructive text-destructive-foreground hover:opacity-90",
        outline: "rounded-md border border-input bg-transparent hover:bg-accent hover:text-accent-foreground",
        // Toolbar/secondary style: flat, bordered, tinted background --
        // matches the reference system's non-CTA buttons.
        secondary:
          "rounded-md bg-[var(--badge-bg)] text-[var(--text-secondary)] border border-[var(--border-primary)] hover:bg-[var(--bg-hover)]",
        ghost: "rounded-md hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        lg: "h-10 px-6",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    )
  },
)
Button.displayName = "Button"

export { Button, buttonVariants }
