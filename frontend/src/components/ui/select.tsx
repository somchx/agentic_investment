import { useEffect, useRef, useState, type ReactNode } from "react"
import { ChevronDown, Check, Search } from "lucide-react"

export interface SelectOption {
  value: string
  label: ReactNode
  disabled?: boolean
  /** Plain text to filter on when `searchable` -- only needed when `label`
   * isn't itself a plain string (e.g. it includes an icon). */
  searchText?: string
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
  /** Shows a filter box pinned to the top of the panel -- turn on for any
   * list long enough that scrolling to find an option isn't practical
   * (e.g. an XBRL tag picker with 1000+ entries). */
  searchable?: boolean
  searchPlaceholder?: string
  noMatchesLabel?: string
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
  searchable = false,
  searchPlaceholder,
  noMatchesLabel = "No matches",
}: SelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const ref = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const current = options.find((o) => o.value === value)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open])

  useEffect(() => {
    if (open && searchable) {
      setQuery("")
      // Let the panel mount before focusing.
      const id = window.setTimeout(() => searchRef.current?.focus(), 0)
      return () => window.clearTimeout(id)
    }
  }, [open, searchable])

  const filteredOptions =
    searchable && query.trim()
      ? options.filter((opt) => {
          const haystack = `${opt.searchText ?? (typeof opt.label === "string" ? opt.label : "")} ${opt.value}`.toLowerCase()
          return haystack.includes(query.trim().toLowerCase())
        })
      : options

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
            {searchable && (
              <div className="sticky top-0 z-10 border-b border-[var(--border-primary)] bg-[var(--bg-card)] p-1.5">
                <div className="flex items-center gap-1.5 rounded border border-[var(--border-primary)] bg-[var(--bg-input)] px-2 py-1">
                  <Search className="h-3.5 w-3.5 flex-none text-[var(--text-ghost)]" />
                  <input
                    ref={searchRef}
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => e.stopPropagation()}
                    placeholder={searchPlaceholder}
                    className="w-full bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-ghost)] focus-visible:outline-none"
                  />
                </div>
              </div>
            )}
            {filteredOptions.length === 0 && (
              <p className="px-3 py-2 text-sm text-[var(--text-ghost)]">{noMatchesLabel}</p>
            )}
            {filteredOptions.map((opt) => (
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
                {opt.value === value && <Check className="h-3.5 w-3.5 shrink-0 text-primary" />}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
