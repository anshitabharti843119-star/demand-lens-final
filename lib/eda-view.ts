import type { EdaData } from "@/lib/types"

export type EdaStoreFilter = "all" | number
export const weekdayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
export const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
export const formatEdaUnits = (value: number) => value.toLocaleString("en-US", { maximumFractionDigits: 1 })
export const formatCompactUnits = (value: number) => Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value)

export function selectEda(data: EdaData, store: EdaStoreFilter) {
  const source = store === "all" ? data : data.by_store?.[store]
  const weekdays = data.weekday_avg.filter(row => store === "all" || row.store === store)
  const weekly = weekdayLabels.flatMap((day, dow) => {
    const matches = weekdays.filter(row => row.dow === dow)
    return matches.length ? [{ day, dow, avg_sales: matches.reduce((sum, row) => sum + row.avg_sales, 0) / matches.length, fill: dow >= 5 ? "var(--primary)" : "var(--history)" }] : []
  })
  const weekend = data.weekend_vs_weekday.filter(row => store === "all" || row.store === store).map(row => ({
    ...row,
    label: `Store ${row.store}`,
    uplift: row.weekday_avg > 0 ? (row.weekend_avg / row.weekday_avg - 1) * 100 : null,
    uplift_label: row.weekday_avg > 0 ? `+${((row.weekend_avg / row.weekday_avg - 1) * 100).toFixed(1)}%` : "—",
  }))
  const weekdayTotal = weekend.reduce((sum, row) => sum + row.weekday_avg, 0)
  const weekendTotal = weekend.reduce((sum, row) => sum + row.weekend_avg, 0)
  return {
    monthly: source?.monthly_total ?? [],
    heatmap: source?.month_year_heatmap ?? [],
    weekly,
    weekend,
    uplift: weekdayTotal > 0 ? (weekendTotal / weekdayTotal - 1) * 100 : null,
  }
}

export type EdaView = ReturnType<typeof selectEda>

export function edaQuality(store: EdaStoreFilter) {
  const series = (store === "all" ? 5 : 1) * 50
  return { rows: 1826 * series, series, missing: 0, duplicates: 0 }
}
