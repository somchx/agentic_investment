// Static GICS-style sector classification for this project's fixed 15-
// company pilot set (PROPOSAL.md section 8) -- a true, verifiable fact
// about each company, not derived/fabricated data, used only for grouping
// the Portfolio Allocation view. Not fetched from any API since there's no
// free source for it without another round of signup/auth plumbing for a
// fact this small and static.
export const SECTOR_BY_TICKER: Record<string, string> = {
  AAPL: "Technology",
  MSFT: "Technology",
  NVDA: "Technology",
  ORCL: "Technology",
  GOOGL: "Communication",
  META: "Communication",
  NFLX: "Communication",
  AMZN: "Consumer",
  TSLA: "Consumer",
  PEP: "Consumer",
  PG: "Consumer",
  KO: "Consumer",
  WMT: "Consumer",
  COST: "Consumer",
  JNJ: "Healthcare",
}

export function sectorFor(ticker: string): string {
  return SECTOR_BY_TICKER[ticker.toUpperCase()] ?? "Other"
}

// Each company's real public web domain (a verifiable fact, same category
// as the sector map above) -- used to fetch its logo from unavatar.io, a
// free, no-key avatar/logo proxy (logo.clearbit.com, this project's first
// choice, no longer resolves -- Clearbit's free Logo API was sunset after
// HubSpot's acquisition; confirmed via direct DNS/curl test before
// switching). Callers must still handle the image failing to load by
// falling back to a plain initials avatar, never a placeholder logo.
export const DOMAIN_BY_TICKER: Record<string, string> = {
  AAPL: "apple.com",
  MSFT: "microsoft.com",
  NVDA: "nvidia.com",
  ORCL: "oracle.com",
  GOOGL: "google.com",
  META: "meta.com",
  NFLX: "netflix.com",
  AMZN: "amazon.com",
  TSLA: "tesla.com",
  PEP: "pepsico.com",
  PG: "pg.com",
  KO: "coca-cola.com",
  WMT: "walmart.com",
  COST: "costco.com",
  JNJ: "jnj.com",
}

export function logoUrlFor(ticker: string): string | null {
  const domain = DOMAIN_BY_TICKER[ticker.toUpperCase()]
  return domain ? `https://unavatar.io/${domain}?size=64&fallback=false` : null
}
