import type { ForecastPoint, Horizon, Mode, SeriesData } from "@/lib/types"

export interface ForecastChartPoint {
  ds: string
  history?: number
  actual?: number
  yhat?: number
  baseline?: number
  lower?: number
  upper?: number
  band?: number
  liveRefit?: number
  liveRefitLower?: number
  liveRefitUpper?: number
}

export function forecastChartData(series: SeriesData, mode: Mode, horizon: Horizon, days: number) {
  const history = mode === "future" ? [...series.history, ...series.backtest.actual] : series.history
  const rows: ForecastChartPoint[] = history.slice(-days).map(point => ({ ds: point.ds, history: point.y }))
  const predictions = (mode === "future" ? series.future.model : series.backtest.model).slice(0, horizon)
  const actuals = new Map(series.backtest.actual.map(point => [point.ds, point.y]))
  const baseline = new Map(series.backtest.baseline.map(point => [point.ds, point.yhat]))
  const last = rows.at(-1)
  if (last) last.yhat = last.history
  return [...rows, ...predictions.map(point => ({
    ds: point.ds, yhat: point.yhat, lower: point.yhat_lower, upper: point.yhat_upper,
    band: point.yhat_upper - point.yhat_lower,
    ...(mode === "backtest" ? { actual: actuals.get(point.ds), baseline: baseline.get(point.ds) } : {}),
  }))]
}

export function forecastVerdict(series: SeriesData, horizon: Horizon) {
  const metrics = horizon === 14 ? series.metrics.h14 : series.metrics.h30
  const improvement = metrics.baseline.mape > 0 ? (metrics.baseline.mape - metrics.model.mape) / metrics.baseline.mape * 100 : 0
  const predictions = new Map(series.backtest.model.slice(0, horizon).map(point => [point.ds, point]))
  const actuals = series.backtest.actual.slice(0, horizon).filter(point => predictions.has(point.ds))
  const covered = actuals.filter(point => {
    const prediction = predictions.get(point.ds)!
    return point.y >= prediction.yhat_lower && point.y <= prediction.yhat_upper
  }).length
  return { metrics, improvement, winner: metrics.model.mape < metrics.baseline.mape ? "model" as const : "baseline" as const, coverage: actuals.length ? covered / actuals.length * 100 : 0 }
}

export const forecastDate = (date: string) => new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(new Date(`${date}T00:00:00Z`))
