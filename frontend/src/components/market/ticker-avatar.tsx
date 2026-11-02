import { useState } from "react"
import { logoUrlFor } from "@/lib/sectors"
import { cn } from "@/lib/utils"

// Real company logo via unavatar.io when we know the company's domain;
// falls back to initials if the logo fails to load (blocked network,
// domain not indexed) rather than showing a broken image.
export function TickerAvatar({ ticker, size = 36 }: { ticker: string; size?: number }) {
  const [failed, setFailed] = useState(false)
  const logoUrl = logoUrlFor(ticker)
  const style = { height: size, width: size }

  if (logoUrl && !failed) {
    return (
      <div
        style={style}
        className="flex flex-none items-center justify-center overflow-hidden rounded-full bg-[var(--bg-hover)]"
      >
        <img src={logoUrl} alt="" className="h-full w-full object-contain p-1" onError={() => setFailed(true)} />
      </div>
    )
  }

  return (
    <div
      style={style}
      className={cn(
        "flex flex-none items-center justify-center rounded-full bg-primary/15 font-mono-num font-bold text-primary",
        size <= 28 ? "text-[10px]" : "text-[11px]",
      )}
    >
      {ticker.slice(0, 2)}
    </div>
  )
}
