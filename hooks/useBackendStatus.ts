/** Hook for backend status monitoring using SWR. */

import useSWR from "swr"
import { health } from "@/lib/api"
// Poll every 30 seconds
const POLL_INTERVAL = 30000

export function useBackendStatus() {
  const healthKey = process.env.NODE_ENV === "production" && !process.env.NEXT_PUBLIC_API_URL
    ? null
    : "health"
  const { data, isLoading, isValidating } = useSWR(healthKey, health, {
    refreshInterval: POLL_INTERVAL,
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
  })

  const backendOnline = data?.ok === true && data.data.status === "ok"
  const errorReason = data?.ok === false ? data.error : null

  return {
    backendOnline,
    backendError: errorReason,
    loading: isLoading || isValidating,
    seriesCount: data?.ok === true ? data.data.series_count : 0,
    prophetAvailable: data?.ok === true ? data.data.prophet_available : false,
  }
}
