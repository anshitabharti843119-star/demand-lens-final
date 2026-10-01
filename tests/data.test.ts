import { test } from "node:test"
import assert from "node:assert/strict"
import { getEda, getManifest, getPortfolio, getRestockInputs, getSeries } from "../lib/data"
import { generateSeries } from "../lib/mock-data"
import { measureErrors } from "../lib/mock-utils"
import { readSelection, selectionQuery } from "../lib/selection"

test("manifest defines all 250 unique series and exact dates", async () => {
  const manifest = await getManifest()
  assert.equal(new Set(manifest.series_ids).size, 250)
  assert.equal(manifest.stores.length, 5)
  assert.equal(manifest.items.length, 50)
  assert.equal(manifest.train_end, "2017-11-30")
  assert.equal(manifest.test_start, "2017-12-01")
  assert.equal(manifest.test_end, "2017-12-31")
  assert.equal(manifest.future_end, "2018-01-30")
})

test("series generation is deterministic and in-memory cache reuses the result", async () => {
  assert.deepEqual(generateSeries("S1_I12"), generateSeries("S1_I12"))
  assert.strictEqual(await getSeries("S1_I12"), await getSeries("S1_I12"))
  assert.notDeepEqual(generateSeries("S1_I12"), generateSeries("S2_I12"))
  await assert.rejects(() => getSeries("S6_I1"))
  await assert.rejects(() => getSeries("S1_I0"))
  await assert.rejects(() => getSeries("S1_I51"))
})

test("all series have correct lengths, ordered dates, measured metrics and credible coverage", async () => {
  const { series_ids } = await getManifest()
  for (const id of series_ids) {
    const series = await getSeries(id)
    assert.equal(series.schema_version, 1)
    assert.equal(series.history.length, 365)
    assert.equal(series.history.at(-1)?.ds, "2017-11-30")
    assert.equal(series.backtest.actual.length, 31)
    assert.equal(series.backtest.actual[0].ds, "2017-12-01")
    assert.equal(series.backtest.actual.at(-1)?.ds, "2017-12-31")
    assert.equal(series.future.model.length, 30)
    assert.equal(series.future.model[0].ds, "2018-01-01")
    assert.equal(series.future.model.at(-1)?.ds, "2018-01-30")
    for (const [key, horizon] of [["h14", 14], ["h30", 30]] as const) {
      for (const source of ["model", "baseline"] as const) {
        const stored = series.metrics[key][source]
        assert.ok(stored.mape > 0 && Number.isFinite(stored.mape), `${id} ${key} ${source} MAPE not positive`)
        assert.ok(stored.rmse > 0 && Number.isFinite(stored.rmse), `${id} ${key} ${source} RMSE not positive`)
        // Recompute from rounded JSON values (Python now also computes on rounded values).
        // h14 = first 14 days; h30 = first 30 days (PRD). MAPE excludes actual==0.
        const actual  = series.backtest.actual.slice(0, horizon)
        const forecast = series.backtest[source].slice(0, horizon)
        const nonZero = actual.filter(p => p.y !== 0)
        const recompMape = nonZero.length
          ? nonZero.reduce((s, p) => s + Math.abs(p.y - forecast[actual.indexOf(p)].yhat) / p.y, 0)
            / nonZero.length * 100
          : 0
        const recompRmse = Math.sqrt(
          actual.reduce((s, p, i) => s + (p.y - forecast[i].yhat) ** 2, 0) / actual.length
        )
        assert.ok(Math.abs(stored.mape - recompMape) <= 0.02,
          `${id} ${key} ${source} MAPE stored=${stored.mape} recomputed=${recompMape.toFixed(4)}`)
        assert.ok(Math.abs(stored.rmse - recompRmse) <= 0.02,
          `${id} ${key} ${source} RMSE stored=${stored.rmse} recomputed=${recompRmse.toFixed(4)}`)
      }
      assert.ok(series.metrics[key].model.mape > 0, id)
      assert.equal(series.metrics[key].model.mape < series.metrics[key].baseline.mape, series.metrics.winner === "model", id)
    }
    // coverage_80 = fraction of first 30 days within the 80% band, on rounded bounds
    const coverage = series.backtest.actual
      .slice(0, 30)
      .filter((p, i) => p.y >= series.backtest.model[i].yhat_lower && p.y <= series.backtest.model[i].yhat_upper)
      .length / 30
    assert.ok(Math.abs(series.metrics.coverage_80 - coverage) <= 0.01,
      `${id} coverage stored=${series.metrics.coverage_80} recomputed=${coverage.toFixed(4)}`)
    assert.ok(coverage >= 0 && coverage <= 1, `${id}: ${coverage}`) // real data: 0.52-1.0, mock: 0.72-0.92
    for (const point of [...series.backtest.model, ...series.future.model]) {
      assert.ok(point.yhat_lower >= 0 && point.yhat_lower <= point.yhat && point.yhat <= point.yhat_upper)
    }
    assert.ok(series.backtest.baseline.every(point => point.yhat === series.backtest.baseline[0].yhat))
  }
})

test("portfolio agrees with series — all 250 have a winner", async () => {
  const portfolio = await getPortfolio()
  assert.equal(portfolio.length, 250)
  // Real data: 250/250 model wins (Prophet vs flat mean). Mock: 212/38.
  const modelWins = portfolio.filter(row => row.winner === "model").length
  const baselineWins = portfolio.filter(row => row.winner === "baseline").length
  assert.equal(modelWins + baselineWins, 250)
  assert.ok(modelWins >= 0 && baselineWins >= 0)
  for (const row of portfolio) {
    const series = await getSeries(row.series_id)
    assert.equal(row.model_mape, series.metrics.h30.model.mape)
    assert.equal(row.baseline_mape, series.metrics.h30.baseline.mape)
    assert.equal(row.improvement_pct > 0, row.winner === "model")
  }
})

test("restock inputs match future series and EDA includes the full date range", async () => {
  const inputs = await getRestockInputs()
  assert.equal(Object.keys(inputs).length, 250)
  for (const [id, input] of Object.entries(inputs)) {
    const series = await getSeries(id)
    assert.deepEqual(input.yhat_future, series.future.model.map(point => point.yhat))
    assert.ok(input.current_stock >= 0 && Number.isInteger(input.current_stock))
    assert.ok(input.avg_daily_28 > 0 && input.sigma_daily > 0)
  }
  const eda = await getEda()
  assert.equal(eda.monthly_total.length, 60)
  assert.equal(eda.monthly_total[0].month, "2013-01")
  assert.equal(eda.monthly_total.at(-1)?.month, "2017-12")
})

test("URL selection validates inputs, round-trips and preserves unrelated query parameters", () => {
  const defaults = { store: 1, item: 12, horizon: 30, mode: "backtest" }
  assert.deepEqual(readSelection(new URLSearchParams()), defaults)
  assert.deepEqual(readSelection(new URLSearchParams("store=6&item=0&h=15&mode=invalid")), defaults)
  const choice = { store: 5, item: 50, horizon: 14, mode: "future" } as const
  const query = selectionQuery(choice, "custom=keep")
  assert.equal(new URLSearchParams(query).get("custom"), "keep")
  assert.deepEqual(readSelection(new URLSearchParams(query)), choice)
})
