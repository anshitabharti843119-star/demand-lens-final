import type { PortfolioRow } from "@/lib/types"

export type PortfolioStoreFilter = "all" | number
export interface PortfolioBin { start: number; end: number; midpoint: number; count: number }

export const formatPortfolioPercent = (value: number) => `${value.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`
export const formatImprovement = (value: number) => `${value > 0 ? "+" : ""}${formatPortfolioPercent(value)}`
export const portfolioForecastHref = (row: Pick<PortfolioRow, "store" | "item">) => `/forecast?store=${row.store}&item=${row.item}&h=30&mode=backtest`

export function portfolioHistogram(rows: PortfolioRow[]): PortfolioBin[] {
  if (!rows.length) return []
  const values = rows.map(row => row.improvement_pct)
  const first = Math.min(-5, Math.floor(Math.min(...values) / 5) * 5)
  const last = Math.max(0, Math.floor(Math.max(...values) / 5) * 5)
  const bins = Array.from({ length: (last - first) / 5 + 1 }, (_, i) => ({ start: first + i * 5, end: first + (i + 1) * 5, midpoint: first + i * 5 + 2.5, count: 0 }))
  for (const value of values) bins[(Math.floor(value / 5) * 5 - first) / 5].count += 1
  return bins
}

export function selectPortfolio(data: PortfolioRow[], store: PortfolioStoreFilter) {
  const rows = data.filter(row => store === "all" || row.store === store)
  const ascending = [...rows].sort((a, b) => a.improvement_pct - b.improvement_pct || a.store - b.store || a.item - b.item)
  const descending = [...rows].sort((a, b) => b.improvement_pct - a.improvement_pct || a.store - b.store || a.item - b.item)
  const count = rows.length
  const wins = rows.filter(row => row.winner === "model").length
  const middle = Math.floor(count / 2)
  const median = !count ? null : count % 2 ? ascending[middle].improvement_pct : (ascending[middle - 1].improvement_pct + ascending[middle].improvement_pct) / 2
  const average = (key: "model_mape" | "baseline_mape") => count ? rows.reduce((sum, row) => sum + row[key], 0) / count : null
  return {
    rows, count, wins, winRate: count ? wins / count * 100 : null,
    median, modelMape: average("model_mape"), baselineMape: average("baseline_mape"),
    histogram: portfolioHistogram(rows),
    top: descending.slice(0, 10),
    // "Worst" = 10 series where the model helped least (lowest improvement_pct).
    // When baseline wins exist they naturally sort first; works correctly with
    // all-model-wins real data too (bottom 10 positives, not an empty list).
    worst: ascending.slice(0, Math.min(10, count)),
    scatterMax: Math.max(5, Math.ceil(Math.max(0, ...rows.flatMap(row => [row.model_mape, row.baseline_mape])) / 5) * 5),
  }
}

export type PortfolioView = ReturnType<typeof selectPortfolio>
