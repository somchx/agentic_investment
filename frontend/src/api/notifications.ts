import { apiClient } from "@/api/client"
import type { AppNotification } from "@/types"

export async function fetchNotifications(): Promise<AppNotification[]> {
  const { data } = await apiClient.get<AppNotification[]>("/notifications")
  return data
}

export async function fetchUnreadCount(): Promise<number> {
  const { data } = await apiClient.get<{ count: number }>("/notifications/unread-count")
  return data.count
}

export async function markNotificationRead(id: number): Promise<void> {
  await apiClient.post(`/notifications/${id}/read`)
}

export async function markAllNotificationsRead(): Promise<void> {
  await apiClient.post("/notifications/read-all")
}

// Free -- reuses check_reason_status, never the paid agent. Lets a user
// re-check their own holdings on demand instead of waiting for the
// hourly scheduled pass.
export async function checkNotificationsNow(): Promise<{ created: AppNotification[] }> {
  const { data } = await apiClient.post<{ created: AppNotification[] }>("/notifications/check-now")
  return data
}
