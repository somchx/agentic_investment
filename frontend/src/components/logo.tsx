import { useId } from "react"

/** Connected market data and an ascending trend, on a neutral slate tile. */
export function LogoMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  const gradientId = useId()
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" className={className} role="img" aria-label="ReasonCheck">
      <defs>
        <linearGradient id={gradientId} x1="4" y1="60" x2="58" y2="4" gradientUnits="userSpaceOnUse">
          <stop stopColor="#1e293b" />
          <stop offset="0.52" stopColor="#334155" />
          <stop offset="1" stopColor="#475569" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="17" fill={`url(#${gradientId})`} />
      <rect x="2.5" y="2.5" width="59" height="59" rx="16.5" stroke="white" strokeOpacity="0.18" />
      <path d="M17 48V40M29 48V35M41 48V28" stroke="white" strokeOpacity="0.28" strokeWidth="5" strokeLinecap="round" />
      <path d="M16 34L28 25L37 30L49 17M41 17H49V25" stroke="white" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="16" cy="34" r="3.5" fill="#93c5fd" />
      <circle cx="28" cy="25" r="3" fill="#93c5fd" />
      <circle cx="37" cy="30" r="3" fill="#93c5fd" />
    </svg>
  )
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={className}>
      <span className="text-[var(--text-primary)]">Reason</span>
      <span className="text-primary">Check</span>
    </span>
  )
}
