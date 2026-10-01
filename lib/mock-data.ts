import type { EdaData, ForecastPoint, Point, RestockInput, SeriesData } from "@/lib/types"
import { calibrateActual, dates, expectedDemand, mean, measureErrors, round, seededRandom, standardDeviation } from "@/lib/mock-utils"

export const mockManifest = {
  stores: [1, 2, 3, 4, 5],
  items: Array.from({ length: 50 }, (_, i) => i + 1),
  series_ids: Array.from({ length: 250 }, (_, i) => `S${Math.floor(i / 50) + 1}_I${i % 50 + 1}`),
  train_end: "2017-11-30",
  test_start: "2017-12-01",
  test_end: "2017-12-31",
  future_end: "2018-01-30",
}

export function parseSeriesId(seriesId: string) {
  const match = /^S([1-5])_I([1-9]|[1-4][0-9]|50)$/.exec(seriesId)
  if (!match) throw new Error(`Invalid series ID: ${seriesId}`)
  return { store: Number(match[1]), item: Number(match[2]) }
}

function modelPoints(actual: Point[], target: number, random: () => number) {
  const errors = actual.map(() => (0.45 + random() * 1.1) * (random() < 0.5 ? -1 : 1))
  const averageError = mean(errors.map(Math.abs))
  return actual.map(({ ds, y }, i) => ({ ds, yhat: round(Math.max(0, y * (1 + errors[i] / averageError * target / 100))) }))
}

export function generateSeries(seriesId: string): SeriesData {
  const { store, item } = parseSeriesId(seriesId)
  const random = seededRandom(seriesId)
  const base = 15 + random() * 75
  const index = (store - 1) * 50 + item - 1
  const baselineWins = (index * 73) % 250 < 38
  const history = dates("2016-12-01", 365).map(ds => ({ ds, y: Math.max(1, Math.round(expectedDemand(ds, base) * (0.84 + random() * 0.32))) }))
  const baselineValue = round(mean(history.slice(-28).map(point => point.y)))
  const rawActual = dates("2017-12-01", 31).map(ds => ({ ds, y: expectedDemand(ds, base) * (0.80 + random() * 0.40) }))
  // The 15.2% baseline-win cases intentionally have lower baseline errors; the stated ranges cannot both hold for a loss.
  const baselineTarget = baselineWins ? 10.5 + random() * 2 : 17 + random() * 7
  const modelTarget = baselineWins ? 14 + random() * 1.5 : 10 + random() * 4.5
  const actual = [
    ...calibrateActual(rawActual.slice(0, 14), baselineValue, baselineTarget),
    ...calibrateActual(rawActual.slice(14), baselineValue, baselineTarget),
  ]
  const predictions = [...modelPoints(actual.slice(0, 14), modelTarget, random), ...modelPoints(actual.slice(14), modelTarget, random)]
  const absoluteErrors = predictions.map((point, i) => Math.abs(point.yhat - actual[i].y)).sort((a, b) => a - b)
  const coveredCount = 24 + Math.floor(random() * 4)
  const halfWidth = (absoluteErrors[coveredCount - 1] + absoluteErrors[coveredCount]) / 2
  const sigma = halfWidth / 1.28
  const withBand = ({ ds, yhat }: { ds: string; yhat: number }): ForecastPoint => ({ ds, yhat, yhat_lower: round(Math.max(0, yhat - 1.28 * sigma)), yhat_upper: round(yhat + 1.28 * sigma) })
  const model = predictions.map(withBand)
  const baseline = actual.map(({ ds }) => ({ ds, yhat: baselineValue }))
  const horizonMetrics = (count: number) => ({ model: measureErrors(actual.slice(0, count), model.slice(0, count)), baseline: measureErrors(actual.slice(0, count), baseline.slice(0, count)) })
  const h14 = horizonMetrics(14)
  const h30 = horizonMetrics(30)
  const coverage = actual.filter((point, i) => point.y >= model[i].yhat_lower && point.y <= model[i].yhat_upper).length / actual.length
  return {
    schema_version: 1, series_id: seriesId, store, item, history,
    backtest: { actual, model, baseline },
    future: { model: dates("2018-01-01", 30).map(ds => withBand({ ds, yhat: round(expectedDemand(ds, base) * (0.94 + random() * 0.12)) })) },
    metrics: { h14, h30, coverage_80: coverage, winner: h30.model.mape < h30.baseline.mape ? "model" : "baseline" },
  }
}

export function generateEda(): EdaData {
  const by_store: Record<number, EdaData> = {}
  const dayList = dates("2013-01-01", 1826)
  const withRolling = (months: EdaData["monthly_total"]) => months.map((point, i) => ({
    ...point,
    ...(i >= 11 ? { rolling_12m: round(mean(months.slice(i - 11, i + 1).map(value => value.sales))) } : {}),
  }))
  for (const store of mockManifest.stores) {
    const random = seededRandom(`eda:store:${store}`)
    const months = new Map<string, { sales: number; days: number }>()
    const weekdays = Array.from({ length: 7 }, () => ({ sales: 0, days: 0 }))
    const storeBase = 50 * mockManifest.items.length * (0.92 + store * 0.025)
    const weekendFactor = (1.26 + store * 0.012) * 0.986 / 1.22
    for (const ds of dayList) {
      const dow = (new Date(`${ds}T00:00:00Z`).getUTCDay() + 6) % 7
      const sales = Math.round(expectedDemand(ds, storeBase) * (dow >= 5 ? weekendFactor : 1) * (0.98 + random() * 0.04))
      const month = ds.slice(0, 7)
      const bucket = months.get(month) ?? { sales: 0, days: 0 }
      bucket.sales += sales
      bucket.days += 1
      months.set(month, bucket)
      weekdays[dow].sales += sales
      weekdays[dow].days += 1
    }
    const periodAverage = (buckets: typeof weekdays) => round(
      buckets.reduce((sum, bucket) => sum + bucket.sales, 0) / buckets.reduce((sum, bucket) => sum + bucket.days, 0) / mockManifest.items.length,
    )
    by_store[store] = {
      monthly_total: withRolling(Array.from(months, ([month, bucket]) => ({ month, sales: bucket.sales }))),
      weekday_avg: weekdays.map((bucket, dow) => ({ store, dow: dow as EdaData["weekday_avg"][number]["dow"], avg_sales: round(bucket.sales / bucket.days / mockManifest.items.length) })),
      weekend_vs_weekday: [{ store, weekday_avg: periodAverage(weekdays.slice(0, 5)), weekend_avg: periodAverage(weekdays.slice(5)) }],
      month_year_heatmap: Array.from(months, ([month, bucket]) => ({ year: Number(month.slice(0, 4)), month: Number(month.slice(5)), avg_sales: round(bucket.sales / bucket.days / mockManifest.items.length) })),
    }
  }
  const stores = Object.values(by_store)
  return {
    monthly_total: withRolling(stores[0].monthly_total.map((point, i) => ({ month: point.month, sales: stores.reduce((sum, store) => sum + store.monthly_total[i].sales, 0) }))),
    weekday_avg: stores.flatMap(store => store.weekday_avg),
    weekend_vs_weekday: stores.flatMap(store => store.weekend_vs_weekday),
    month_year_heatmap: stores[0].month_year_heatmap!.map((point, i) => ({ ...point, avg_sales: round(mean(stores.map(store => store.month_year_heatmap![i].avg_sales))) })),
    by_store,
  }
}

export function generateRestockInput(series: SeriesData): RestockInput {
  const random = seededRandom(`${series.series_id}:inventory`)
  const recentSales = series.backtest.actual.slice(-28).map(point => point.y)
  const dailyMean = mean(recentSales)
  return {
    store: series.store, item: series.item,
    current_stock: Math.round(dailyMean * (0.4 + random() * 42)),
    avg_daily_28: dailyMean,
    sigma_daily: standardDeviation(recentSales),
    yhat_future: series.future.model.map(point => point.yhat),
  }
}
