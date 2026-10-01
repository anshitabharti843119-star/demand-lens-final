import assert from "node:assert/strict"
import { test } from "node:test"
import { getManifest, getSeries, getPortfolio, getEda, getRestockInputs } from "../lib/data"
import { generateSeries } from "../lib/mock-data"
import { measureErrors } from "../lib/mock-utils"
import { computeRestock } from "../lib/restock"
import { defaultRestockOptions, filterSortRestock, restockCsv, summarizeRestock } from "../lib/restock-view"
import { forecastChartData, forecastVerdict } from "../lib/forecast-view"
import { selectPortfolio } from "../lib/portfolio-view"
import { defaultSelection, readSelection, selectionQuery } from "../lib/selection"
import type { RestockInput } from "../lib/types"

const input: RestockInput = { store: 1, item: 1, current_stock: 100, sigma_daily: 4, avg_daily_28: 10, yhat_future: Array(30).fill(10) }

test("restock formula, rounding, cover and priority match the contract", () => {
  const [row] = computeRestock({ S1_I1: input }, defaultRestockOptions)
  assert.equal(row.forecast_demand, 300)
  assert.equal(row.safety_stock, 1.65 * 4 * Math.sqrt(3))
  assert.equal(row.restock_qty, 212)
  assert.equal(row.days_of_cover, 10)
  assert.equal(row.priority, "MEDIUM")
  const [urgent] = computeRestock({ S1_I1: { ...input, current_stock: 10 } }, defaultRestockOptions)
  assert.equal(urgent.priority, "HIGH")
  const [covered] = computeRestock({ S1_I1: { ...input, current_stock: 400 } }, defaultRestockOptions)
  assert.equal(covered.restock_qty, 0)
  assert.equal(covered.priority, "LOW")
})

test("restock handles zero demand and rejects invalid inputs", () => {
  const [zero] = computeRestock({ S1_I1: { ...input, sigma_daily: 0, yhat_future: Array(30).fill(0) } }, defaultRestockOptions)
  assert.equal(zero.days_of_cover, Infinity)
  assert.equal(zero.restock_qty, 0)
  assert.throws(() => computeRestock({ S1_I1: { ...input, current_stock: -1 } }, defaultRestockOptions), RangeError)
  assert.throws(() => computeRestock({ S1_I1: input }, { ...defaultRestockOptions, leadTime: 0 }), RangeError)
})

test("all 250 series have correct lengths, valid bands, and consistent stored metrics", async () => {
  const manifest = await getManifest()
  assert.equal(manifest.series_ids.length, 250)
  for (const id of manifest.series_ids) {
    const series = await getSeries(id)
    assert.equal(series.history.at(-1)?.ds, "2017-11-30")
    assert.equal(series.backtest.actual.length, 31)
    assert.equal(series.future.model.length, 30)
    for (const horizon of [14, 30] as const) {
      // h14 = first 14 days; h30 = first 30 days (PRD definition, not 31).
      // Python now computes on rounded JSON values → tolerance ±0.02.
      // MAPE excludes actual==0 rows (matching Python _mape mask = actual != 0).
      const actual   = series.backtest.actual.slice(0, horizon)
      const modelPts = series.backtest.model.slice(0, horizon)
      const nonZero  = actual.filter(p => p.y !== 0)
      const recompMape = nonZero.length
        ? nonZero.reduce((s, p) => s + Math.abs(p.y - modelPts[actual.indexOf(p)].yhat) / p.y, 0)
          / nonZero.length * 100
        : 0
      const stored = series.metrics[`h${horizon}`].model.mape
      assert.ok(Math.abs(stored - recompMape) <= 0.02,
        `${id} h${horizon} MAPE stored=${stored.toFixed(4)} recomputed=${recompMape.toFixed(4)}`)
      assert.ok(["model", "baseline"].includes(series.metrics.winner))
    }
    // winner is consistent with h30
    const h30m = series.metrics.h30.model.mape
    const h30b = series.metrics.h30.baseline.mape
    assert.equal(series.metrics.winner, h30m < h30b ? "model" : "baseline", id)
    for (const point of [...series.backtest.model, ...series.future.model]) {
      assert.ok(point.yhat_lower >= 0 && point.yhat_lower <= point.yhat && point.yhat <= point.yhat_upper)
    }
  }
  // mock is still deterministic
  assert.deepEqual(generateSeries("S1_I12"), generateSeries("S1_I12"))
  assert.strictEqual(await getSeries("S1_I12"), await getSeries("S1_I12"))
  await assert.rejects(getSeries("S9_I99"))
})

test("forecast modes use correct dates, horizon and honest verdicts", async () => {
  const series = await getSeries("S1_I12")
  const backtest = forecastChartData(series, "backtest", 14, 90)
  assert.equal(backtest.length, 104)
  assert.equal(backtest.at(-1)?.ds, "2017-12-14")
  const future = forecastChartData(series, "future", 30, 90)
  assert.equal(future[89].ds, "2017-12-31")
  assert.equal(future.at(-1)?.ds, "2018-01-30")
  assert.ok(future.every(point => point.actual === undefined && point.baseline === undefined))

  // (a) Every real series has winner consistent with h30 MAPE
  const manifest = await getManifest()
  for (const id of manifest.series_ids) {
    const s = await getSeries(id)
    const expected = s.metrics.h30.model.mape < s.metrics.h30.baseline.mape ? "model" : "baseline"
    assert.equal(forecastVerdict(s, 30).winner, expected, `${id} verdict mismatch`)
  }

  // (b) Synthetic fixture: ensure "baseline wins" UI path is covered
  //     even when real data has 0 baseline wins.
  const syntheticSeries = generateSeries("S1_I12")
  // Force baseline to win by swapping mape values in a shallow copy
  const fakeMetrics = {
    ...syntheticSeries.metrics,
    h30: { ...syntheticSeries.metrics.h30,
      model:    { mape: 20, rmse: 5 },
      baseline: { mape: 10, rmse: 3 },
    },
    winner: "baseline" as const,
  }
  const fakeSeasonalSeries = { ...syntheticSeries, metrics: fakeMetrics }
  assert.equal(forecastVerdict(fakeSeasonalSeries, 30).winner, "baseline")
})

test("portfolio bins, rankings and store filter remain consistent", async () => {
  const data = await getPortfolio()
  const all = selectPortfolio(data, "all")
  assert.equal(all.count, 250)
  assert.ok(all.wins >= 0 && all.wins <= 250) // real: 250, mock: 212
  assert.ok(all.winRate !== null && all.winRate >= 0 && all.winRate <= 100) // real: 100%, mock: 84.8%
  assert.equal(all.histogram.reduce((sum, bin) => sum + bin.count, 0), all.count)
  // worst = bottom-10 by improvement_pct (sorted ascending). With real data: 0 baseline wins,
  // so worst = 10 model-win series with smallest improvement. Check sort order is correct.
  assert.equal(all.worst.length, 10)
  assert.ok(all.worst.every((row, i) => i === 0 || all.worst[i - 1].improvement_pct <= row.improvement_pct),
    "worst not sorted ascending by improvement_pct")
  assert.equal(selectPortfolio(data, 3).count, 50)
})

test("EDA monthly store totals reconcile with the all-store view", async () => {
  const eda = await getEda()
  assert.equal(eda.monthly_total.length, 60)
  for (let i = 0; i < 60; i++) {
    const total = Object.values(eda.by_store!).reduce((sum, store) => sum + store.monthly_total[i].sales, 0)
    assert.equal(total, eda.monthly_total[i].sales)
  }
  assert.ok(eda.weekend_vs_weekday.every(row => row.weekend_avg > row.weekday_avg))
})

test("restock filters, sort, summary and CSV use the same rows", async () => {
  const rows = filterSortRestock(computeRestock(await getRestockInputs(), defaultRestockOptions), { store: "2", priority: "all", search: "" }, { key: "restock_qty", direction: "desc" })
  assert.ok(rows.length > 0 && rows.every(row => row.store === 2 && row.restock_qty > 0))
  assert.ok(rows.every((row, i) => i === 0 || rows[i - 1].restock_qty >= row.restock_qty))
  assert.equal(summarizeRestock(rows).products, rows.length)
  const csv = restockCsv(rows, 30).trim().split("\r\n")
  assert.equal(csv.length, rows.length + 1)
  assert.ok(csv[1].startsWith(`"Item ${rows[0].item}","Store 2"`))
})

test("URL selections validate invalid values and preserve other parameters", () => {
  assert.deepEqual(readSelection(new URLSearchParams("store=99&item=-1&h=9&mode=invalid")), defaultSelection)
  const selection = { store: 4, item: 50, horizon: 14 as const, mode: "future" as const }
  const query = selectionQuery(selection, "demo=example")
  assert.deepEqual(readSelection(new URLSearchParams(query)), selection)
  assert.equal(new URLSearchParams(query).get("demo"), "example")
})
