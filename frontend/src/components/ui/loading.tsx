export function Loading({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-center">
      <div
        className="h-6 w-6 animate-spin rounded-full border-2"
        style={{ borderColor: "var(--accent-blue)", borderTopColor: "transparent" }}
      />
      {label && <p className="text-xs text-[var(--text-muted)]">{label}</p>}
    </div>
  )
}
