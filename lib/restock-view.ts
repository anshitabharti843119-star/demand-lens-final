import type { RestockRow } from "@/lib/types"
import type { RestockOptions } from "@/lib/restock"

export const defaultRestockOptions: RestockOptions = { horizon: 30, serviceLevel: 0.95, leadTime: 3, stockMultiplier: 1 }
export interface RestockFilters { store: string; priority: string; search: string }
export const defaultRestockFilters: RestockFilters = { store: "all", priority: "all", search: "" }
export type RestockSortKey = Exclude<keyof RestockRow, "series_id">
export interface RestockSort { key: RestockSortKey; direction: "asc" | "desc" }
export const defaultRestockSort: RestockSort = { key: "days_of_cover", direction: "asc" }
const priorityRank = { HIGH: 0, MEDIUM: 1, LOW: 2 }
const unitsFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 })
const coverFormatter = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 })
export const formatUnits = (value: number) => unitsFormatter.format(value)
export const formatCover = (value: number) => Number.isFinite(value) ? coverFormatter.format(value) : "∞"

export function filterSortRestock(rows: RestockRow[], filters: RestockFilters, sort: RestockSort) {
  const query = filters.search.trim().replace(/^item\s*/i, "")
  return rows.filter(row => row.restock_qty > 0 && (filters.store === "all" || row.store === Number(filters.store)) && (filters.priority === "all" || row.priority === filters.priority) && String(row.item).includes(query)).sort((a, b) => {
    const left = sort.key === "priority" ? priorityRank[a.priority] : a[sort.key]
    const right = sort.key === "priority" ? priorityRank[b.priority] : b[sort.key]
    const order = left < right ? -1 : left > right ? 1 : 0
    return order * (sort.direction === "asc" ? 1 : -1) || a.series_id.localeCompare(b.series_id)
  })
}

export function summarizeRestock(rows: RestockRow[]) {
  return { products: rows.length, units: rows.reduce((sum, row) => sum + row.restock_qty, 0), high: rows.filter(row => row.priority === "HIGH").length, cover: rows.length ? rows.reduce((sum, row) => sum + row.days_of_cover, 0) / rows.length : 0 }
}

export function restockCsv(rows: RestockRow[], horizon: number) {
  const header = ["Product", "Store", "Current stock", `Forecast demand (${horizon} days)`, "Safety stock", "Restock qty", "Days of cover", "Priority"]
  const quote = (value: string) => `"${value.replaceAll('"', '""')}"`
  const body = rows.map(row => [`Item ${row.item}`, `Store ${row.store}`, formatUnits(row.current_stock), formatUnits(row.forecast_demand), formatUnits(row.safety_stock), formatUnits(row.restock_qty), formatCover(row.days_of_cover), row.priority])
  return [header, ...body].map(row => row.map(quote).join(",")).join("\r\n") + "\r\n"
}

export function downloadRestockCsv(rows: RestockRow[], horizon: number) {
  const url = URL.createObjectURL(new Blob(["\uFEFF", restockCsv(rows, horizon)], { type: "text/csv;charset=utf-8;" }))
  const date = new Date()
  const stamp = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`
  const link = document.createElement("a")
  link.href = url
  link.download = `restock_${stamp}.csv`
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
