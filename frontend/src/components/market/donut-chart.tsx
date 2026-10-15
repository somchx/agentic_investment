import type { ReactNode } from "react"

export interface DonutSegment {
  label: string
  value: number
  colorClass: string
}

// Dependency-free SVG ring chart (stroke-dasharray trick on a single
// circle per segment) -- same reasoning as PriceChart: a chart this simple
// doesn't need a charting library. `children` render in the hole.
export function DonutChart({ segments, size = 140, children }: { segments: DonutSegment[]; size?: number; children?: ReactNode }) {
  const total = segments.reduce((sum, s) => sum + s.value, 0)
  const stroke = size * 0.12
  const radius = size / 2 - stroke / 2 - 2
  const circumference = 2 * Math.PI * radius
  // A small surface-coloured gap between segments so adjacent ones stay distinct.
  const gap = segments.length > 1 ? 2 : 0
  let offset = 0

  if (total <= 0) return null

  return (
    <div className="relative flex-none" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} className="h-full w-full">
        <g transform={`translate(${size / 2}, ${size / 2}) rotate(-90)`}>
          <circle r={radius} fill="none" strokeWidth={stroke} stroke="var(--bg-hover)" />
          {segments.map((s, i) => {
            const dash = Math.max((s.value / total) * circumference - gap, 0.5)
            const el = (
              <circle
                key={i}
                r={radius}
                fill="none"
                strokeWidth={stroke}
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={-offset}
                className={s.colorClass}
                stroke="currentColor"
              >
                <title>{s.label}</title>
              </circle>
            )
            offset += (s.value / total) * circumference
            return el
          })}
        </g>
      </svg>
      {children && <div className="absolute inset-0 flex flex-col items-center justify-center text-center">{children}</div>}
    </div>
  )
}
