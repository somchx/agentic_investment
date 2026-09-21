import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  checkNotificationsNow,
  fetchNotifications,
  fetchUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/api/notifications"
import { queryKeys } from "@/hooks/query-keys"

// Polled, not pushed -- simplest thing that works for a single-instance
// local app. 60s is frequent enough to feel live without hammering the
// (free) endpoint.
const POLL_MS = 60_000

export function useNotifications() {
  return useQuery({
    queryKey: queryKeys.notifications,
    queryFn: fetchNotifications,
    refetchInterval: POLL_MS,
  })
}

export function useUnreadCount() {
  return useQuery({
    queryKey: queryKeys.notificationsUnreadCount,
    queryFn: fetchUnreadCount,
    refetchInterval: POLL_MS,
  })
}

function useInvalidateNotifications() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.notifications })
    queryClient.invalidateQueries({ queryKey: queryKeys.notificationsUnreadCount })
  }
}

export function useMarkNotificationRead() {
  const invalidate = useInvalidateNotifications()
  return useMutation({
    mutationFn: (id: number) => markNotificationRead(id),
    onSuccess: invalidate,
  })
}

export function useMarkAllNotificationsRead() {
  const invalidate = useInvalidateNotifications()
  return useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: invalidate,
  })
}

export function useCheckNotificationsNow() {
  const invalidate = useInvalidateNotifications()
  return useMutation({
    mutationFn: checkNotificationsNow,
    onSuccess: invalidate,
  })
}
