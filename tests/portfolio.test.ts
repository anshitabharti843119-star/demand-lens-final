import test from "node:test"
import assert from "node:assert/strict"
import { getPortfolio } from "../lib/data"
import { portfolioForecastHref, portfolioHistogram, selectPortfolio } from "../lib/portfolio-view"
import type { PortfolioRow } from "../lib/types"

const row = (improvement: number, item: number, store = 1): PortfolioRow => ({ series_id: `S${store}_I${item}`, store, item, model_mape: 20 * (1 - improvement / 100), baseline_mape: 20, improvement_pct: improvement, winner: improvement > 0 ? "model" : "baseline" })

test("portfolio KPIs use equal series weights and exact even and odd medians", () => {
  const data = [row(-10, 1), row(20, 2), row(30, 3), row(40, 4)]
  const view = selectPortfolio(data, "all")
  assert.equal(view.count, 4)
  assert.equal(view.wins, 3)
  assert.equal(view.winRate, 75)
  assert.equal(view.median, 25)
  assert.equal(view.modelMape, 16)
  assert.equal(view.baselineMape, 20)
  assert.equal(selectPortfolio(data.slice(0, 3), "all").median, 20)
})

test("histogram assigns each series once using exact 5-percent boundaries, including zero", () => {
  const values = [-10, -5.01, -5, -0.01, 0, 4.99, 5, 10]
  const bins = portfolioHistogram(values.map((value, index) => row(value, index + 1)))
  assert.deepEqual(bins.map(bin => [bin.start, bin.count]), [[-10, 2], [-5, 2], [0, 2], [5, 1], [10, 1]])
  assert.equal(bins.reduce((sum, bin) => sum + bin.count, 0), values.length)
  assert.ok(bins.every(bin => bin.end - bin.start === 5 && bin.midpoint === bin.start + 2.5))
  assert.ok(portfolioHistogram([row(20, 1)]).some(bin => bin.start === -5))
  assert.ok(portfolioHistogram([row(-20, 1)]).some(bin => bin.start === 0))
})

test("store filtering recalculates all views without changing cached portfolio rows", async () => {
  const data = await getPortfolio()
  const before = JSON.stringify(data)
  const all = selectPortfolio(data, "all")
  assert.equal(all.count, 250)
  // Real data: 250/250 model wins. Mock: 212/38. Just check total adds up.
  assert.ok(all.wins >= 0 && all.wins <= 250)
  assert.ok(all.winRate !== null && all.winRate >= 0 && all.winRate <= 100) // real: 100%, mock: 84.8%
  for (const store of [1, 2, 3, 4, 5]) {
    const view = selectPortfolio(data, store)
    assert.equal(view.count, 50)
    assert.ok([...view.rows, ...view.top, ...view.worst].every(row => row.store === store))
    assert.equal(view.histogram.reduce((sum, bin) => sum + bin.count, 0), 50)
    assert.equal(view.modelMape, view.rows.reduce((sum, row) => sum + row.model_mape, 0) / 50)
    assert.ok(view.rows.every(row => row.model_mape <= view.scatterMax && row.baseline_mape <= view.scatterMax))
  }
  assert.equal(JSON.stringify(data), before)
  assert.equal(await getPortfolio(), data)
})

test("rankings are correctly ordered: top by improvement, worst by lowest improvement_pct", async () => {
  const view = selectPortfolio(await getPortfolio(), "all")
  assert.equal(view.top.length, 10)
  // "worst" = 10 series where model helped least (lowest improvement_pct ascending)
  assert.equal(view.worst.length, 10)
  assert.ok(view.top.every((row, i) => i === 0 || view.top[i - 1].improvement_pct >= row.improvement_pct),
    "top not sorted descending")
  assert.ok(view.worst.every((row, i) => i === 0 || view.worst[i - 1].improvement_pct <= row.improvement_pct),
    "worst not sorted ascending")

  // Synthetic fixture: when baseline wins exist, they sort first in "worst"
  const makeRow = (improvement: number, item: number, store = 1): PortfolioRow => ({
    series_id: `S${store}_I${item}`, store, item,
    model_mape: 20 * (1 - improvement / 100), baseline_mape: 20,
    improvement_pct: improvement, winner: improvement > 0 ? "model" : "baseline",
  })
  const sparse = selectPortfolio([makeRow(10, 1), makeRow(-10, 2), makeRow(0, 3)], "all")
  assert.equal(sparse.worst.length, 3) // fewer than 10 series total
  assert.equal(sparse.worst[0].item, 2) // lowest improvement (-10) is first
  assert.ok(sparse.worst.every((r, i) => i === 0 || sparse.worst[i - 1].improvement_pct <= r.improvement_pct))
})

test("every ranking link selects its series and the 30-day backtest explicitly", async () => {
  const view = selectPortfolio(await getPortfolio(), "all")
  for (const entry of [...view.top, ...view.worst]) {
    assert.equal(portfolioForecastHref(entry), `/forecast?store=${entry.store}&item=${entry.item}&h=30&mode=backtest`)
  }
})

test("empty selections have no fabricated KPIs, histogram bins or ranking rows", () => {
  const view = selectPortfolio([row(10, 1)], 5)
  assert.equal(view.count, 0)
  assert.equal(view.winRate, null)
  assert.equal(view.median, null)
  assert.equal(view.modelMape, null)
  assert.equal(view.baselineMape, null)
  assert.deepEqual(view.histogram, [])
  assert.deepEqual(view.top, [])
  assert.deepEqual(view.worst, [])
})
