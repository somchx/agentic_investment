// Centralized query key factory so invalidation stays consistent across hooks.
export const queryKeys = {
  companies: ["companies"] as const,
  reasons: (ticker?: string) => (ticker ? (["reasons", ticker] as const) : (["reasons"] as const)),
  xbrlTags: (ticker: string) => ["xbrl-tags", ticker] as const,
  report: (ticker: string) => ["report", ticker] as const,
  profiles: ["profiles"] as const,
  screen: (reasonKeys: string[]) => ["screen", ...[...reasonKeys].sort()] as const,
  positions: ["positions"] as const,
  portfolioSummary: ["portfolio", "summary"] as const,
  me: ["auth", "me"] as const,
  notifications: ["notifications"] as const,
  notificationsUnreadCount: ["notifications", "unread-count"] as const,
  conversations: ["conversations"] as const,
  conversation: (id: number) => ["conversations", id] as const,
}
