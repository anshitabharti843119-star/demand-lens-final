import type { Horizon, RestockInput, RestockRow } from "@/lib/types"

export interface RestockOptions {
  horizon: Horizon
  serviceLevel: 0.9 | 0.95 | 0.99
  leadTime: number
  stockMultiplier: number
}

const zScores = { 0.9: 1.28, 0.95: 1.65, 0.99: 2.33 } as const
const nonnegative = (value: number) => Number.isFinite(value) && value >= 0

export function computeRestock(inputs: Record<string, RestockInput>, opts: RestockOptions): RestockRow[] {
  const { horizon, serviceLevel, leadTime, stockMultiplier } = opts
  if (![14, 30].includes(horizon) || !(serviceLevel in zScores) || !Number.isFinite(leadTime) || leadTime <= 0 || !nonnegative(stockMultiplier)) {
    throw new RangeError("Invalid restock options")
  }
  return Object.entries(inputs).map(([series_id, input]): RestockRow => {
    if (!nonnegative(input.current_stock) || !nonnegative(input.sigma_daily) || input.yhat_future.length < horizon || !input.yhat_future.slice(0, horizon).every(nonnegative)) {
      throw new RangeError(`Invalid restock input for ${series_id}`)
    }
    const current_stock = input.current_stock * stockMultiplier
    const forecast_demand = input.yhat_future.slice(0, horizon).reduce((sum, demand) => sum + demand, 0)
    const safety_stock = zScores[serviceLevel] * input.sigma_daily * Math.sqrt(leadTime)
    const restock_qty = Math.max(0, Math.ceil(forecast_demand + safety_stock - current_stock))
    const days_of_cover = forecast_demand > 0 ? current_stock / (forecast_demand / horizon) : Infinity
    return {
      series_id, store: input.store, item: input.item, current_stock,
      forecast_demand, safety_stock, restock_qty, days_of_cover,
      priority: days_of_cover < leadTime ? "HIGH" : days_of_cover < horizon ? "MEDIUM" : "LOW",
    }
  }).sort((a, b) => a.days_of_cover - b.days_of_cover || a.series_id.localeCompare(b.series_id))
}
