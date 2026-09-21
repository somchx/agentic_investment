/** ReasonCheck brand mark + wordmark -- dependency-free, theme-adaptive
 * inline SVG, same technique as the reference design system: an open ring
 * in `currentColor` (legible on dark & light) with an accent-colored motif
 * that pops in both themes. Here the motif is a check-mark trend line
 * (evidence re-confirmed) instead of a heartbeat pulse -- distinct content
 * for this project's own subject, same construction. */

const ACCENT = "#2a7fff"

export function LogoMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" className={className} role="img" aria-label="ReasonCheck">
      {/* open ring (gap on the right where the check-line exits) */}
      <path
        d="M53.75 42.14 A24 24 0 1 1 53.75 21.86"
        stroke="currentColor"
        strokeWidth="5"
        strokeLinecap="round"
        fill="none"
        opacity="0.88"
      />
      {/* evidence check-line: dip then rise, ending in a confirming tick */}
      <polyline
        points="10,26 22,26 27,36 34,16 41,30 46,30 54,20"
        stroke={ACCENT}
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <circle cx="54" cy="20" r="4.2" fill={ACCENT} />
    </svg>
  )
}

/** Two-tone "ReasonCheck" wordmark -- "Reason" in the foreground color,
 * "Check" in the brand accent blue, matching the reference system's
 * wordmark treatment exactly. */
export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={className}>
      <span className="text-[var(--text-primary)]">Reason</span>
      <span style={{ color: ACCENT }}>Check</span>
    </span>
  )
}
