import { useId, useMemo } from "react"
import type { PricePoint } from "@/types"

interface PriceChartProps {
  data: PricePoint[]
  height?: number
  className?: string
  /** Compact mode: no padding for labels, used as an inline sparkline (table rows, summary cards). */
  sparkline?: boolean
}

// Dependency-free SVG area chart -- gradient fill fading to transparent,
// matching the reference dashboards' chart style, without pulling in a
// charting library for what is otherwise a single line + fill. Scales to
// its container's width via viewBox; height is fixed (px) since these
// charts sit in fixed-height card slots.
export function PriceChart({ data, height = 220, className, sparkline = false }: PriceChartProps) {
  const gradientId = useId()
  const width = 600
  const padY = sparkline ? 2 : 10

  const { pathD, areaD, isUp } = useMemo(() => {
    if (data.length < 2) return { pathD: "", areaD: "", isUp: true }
    const closes = data.map((d) => d.close)
    const min = Math.min(...closes)
    const max = Math.max(...closes)
    const range = max - min || 1
    const drawableHeight = height - padY * 2
    const stepX = width / (data.length - 1)
    const points = closes.map((c, i) => {
      const x = i * stepX
      const y = padY + drawableHeight - ((c - min) / range) * drawableHeight
      return [x, y] as const
    })
    const pathD = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ")
    const areaD = `${pathD} L${width},${height} L0,${height} Z`
    return { pathD, areaD, isUp: closes[closes.length - 1] >= closes[0] }
  }, [data, height, padY])

  if (data.length < 2) {
    return (
      <div
        className={className}
        style={{ height }}
        aria-hidden
      />
    )
  }

  const colorClass = isUp ? "text-status-supported" : "text-status-broken"

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={className}
      style={{ width: "100%", height }}
    >
      <defs>
        <linearGradient id={gradientId} className={colorClass} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity={sparkline ? 0.25 : 0.35} />
          <stop offset="100%" stopColor="currentColor" stopOpacity={0} />
        </linearGradient>
      </defs>
      <g className={colorClass}>
        <path d={areaD} fill={`url(#${gradientId})`} stroke="none" />
        <path d={pathD} fill="none" stroke="currentColor" strokeWidth={sparkline ? 1.5 : 2} strokeLinejoin="round" strokeLinecap="round" />
      </g>
    </svg>
  )
}
