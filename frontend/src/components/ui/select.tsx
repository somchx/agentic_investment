import { useEffect, useRef, useState, type ReactNode } from "react"
import { ChevronDown, Check } from "lucide-react"

export interface SelectOption {
  value: string
  label: ReactNode
  disabled?: boolean
}

interface SelectProps {
  value: string | undefined
  onChange: (value: string) => void
  options: SelectOption[]
  /** Shown when no option matches `value` (rare -- usually the first option covers this). */
  placeholder?: string
  disabled?: boolean
  /** Classes for the trigger button -- pass the same classes the old `<select>` used. */
  className?: string
  /** Dropdown panel alignment relative to the trigger. */
  align?: "left" | "right"
  /** Extra classes for the dropdown panel, e.g. to set a fixed width. */
  panelClassName?: string
  title?: string
  id?: string
}

/**
 * Drop-in replacement for a native `<select>`. Native selects hand dropdown
 * positioning entirely to the OS/browser, which on mobile can render the
 * option list nowhere near the trigger. This renders and positions its own
 * panel so it always opens attached to the button that opened it.
 */
export function Select({
  value,
  onChange,
  options,
  placeholder,
  disabled,
  className,
  align = "left",
  panelClassName,
  title,
  id,
}: SelectProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const current = options.find((o) => o.value === value)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open])

  const base =
    className ??
    "flex items-center justify-between gap-2 rounded border border-[var(--border-primary)] bg-[var(--bg-input)] px-3 py-1.5 text-sm text-[var(--text-primary)] disabled:opacity-60"

  return (
    <div className="relative inline-block" ref={ref}>
      <button id={id} type="button" title={title} disabled={disabled} onClick={() => setOpen((v) => !v)} className={base}>
        <span className="truncate">{current?.label ?? placeholder ?? value ?? ""}</span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-[var(--text-ghost)]" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div
            className={
              panelClassName ??
              `absolute ${align === "right" ? "right-0" : "left-0"} top-full z-50 mt-1 min-w-full w-max max-w-[min(90vw,20rem)] max-h-72 overflow-y-auto rounded-lg border border-[var(--border-primary)] bg-[var(--bg-card)] py-1 shadow-xl`
            }
          >
            {options.map((opt) => (
              <button
                key={opt.value}
                type="button"
                disabled={opt.disabled}
                onClick={() => {
                  onChange(opt.value)
                  setOpen(false)
                }}
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm text-[var(--text-primary)] hover:bg-[var(--bg-hover)] disabled:opacity-50"
              >
                <span className="truncate">{opt.label}</span>
                {opt.value === value && <Check className="h-3.5 w-3.5 shrink-0 text-[var(--accent-blue)]" />}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
