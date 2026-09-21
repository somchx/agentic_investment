import { useQuery } from "@tanstack/react-query"
import { runScreen } from "@/api/screen"
import { queryKeys } from "@/hooks/query-keys"

// Screening is mechanical (zero AI), so unlike ask-agent/personalize it's
// safe to fire on demand without a cost-confirmation dialog. Still gated
// behind an explicit "Run screen" click, driven by `enabled`.
export function useScreen(reasonKeys: string[]) {
  return useQuery({
    queryKey: queryKeys.screen(reasonKeys),
    queryFn: () => runScreen(reasonKeys),
    enabled: reasonKeys.length > 0,
  })
}
