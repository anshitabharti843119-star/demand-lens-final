import { test } from "node:test"
import assert from "node:assert/strict"
import { getEda } from "../lib/data"
import { edaQuality, selectEda } from "../lib/eda-view"
import { round } from "../lib/mock-utils"

test("EDA covers every month, weekday and store with correct structure", async () => {
  const data = await getEda()
  // Cache returns same object
  assert.strictEqual(data, await getEda())
  // Structure checks
  assert.equal(data.monthly_total.length, 60)
  assert.equal(data.weekday_avg.length, 35)
  assert.equal(data.weekend_vs_weekday.length, 5)
  assert.equal(data.month_year_heatmap?.length, 60)
  // Exact date range: 2013-01 through 2017-12
  assert.equal(data.monthly_total[0].month, "2013-01")
  assert.equal(data.monthly_total.at(-1)!.month, "2017-12")
  assert.deepEqual(
    data.monthly_total.map(r => r.month),
    Array.from({ length: 60 }, (_, i) => `${2013 + Math.floor(i / 12)}-${String(i % 12 + 1).padStart(2, "0")}`)
  )
  // by_store has keys "1"…"5" and each store has same structure
  assert.deepEqual(Object.keys(data.by_store ?? {}), ["1", "2", "3", "4", "5"])
  for (const store of [1, 2, 3, 4, 5]) {
    const s = data.by_store![store]
    assert.equal(s.monthly_total.length, 60, `store ${store} monthly_total`)
    assert.equal(s.weekday_avg.length, 7, `store ${store} weekday_avg`)
    assert.equal(s.weekend_vs_weekday.length, 1, `store ${store} wvw`)
    assert.equal(s.month_year_heatmap?.length, 60, `store ${store} heatmap`)
    // store-filtered view matches by_store
    assert.deepEqual(data.weekday_avg.filter(r => r.store === store).map(r => r.dow), [0, 1, 2, 3, 4, 5, 6])
  }
  // every month has positive integer sales
  for (const m of data.monthly_total) {
    assert.ok(m.sales > 0 && Number.isInteger(m.sales), `month ${m.month} sales=${m.sales}`)
  }
})

test("monthly totals equal store sums and trailing averages require 12 complete months", async () => {
  const data = await getEda()
  const stores = Object.values(data.by_store!)
  for (const [i, month] of data.monthly_total.entries()) {
    assert.equal(month.sales, stores.reduce((sum, store) => sum + store.monthly_total[i].sales, 0))
  }
  for (const source of [data, ...stores]) {
    source.monthly_total.forEach((month, i) => {
      assert.ok(month.sales > 0 && Number.isInteger(month.sales))
      if (i < 11) assert.equal(month.rolling_12m, undefined)
      else assert.equal(month.rolling_12m, round(source.monthly_total.slice(i - 11, i + 1).reduce((sum, row) => sum + row.sales, 0) / 12))
    })
  }
})

test("EDA has upward annual trends, summer peaks and positive weekend uplift (10–80%)", async () => {
  const data = await getEda()
  for (const source of [data, ...Object.values(data.by_store!)]) {
    let previousAnnual = 0
    for (let year = 2013; year <= 2017; year++) {
      const months = source.monthly_total.filter(row => row.month.startsWith(String(year)))
      const annual = months.reduce((sum, row) => sum + row.sales, 0)
      assert.ok(annual > previousAnnual, `year ${year} not growing`)
      previousAnnual = annual
      const peak = months.reduce((a, b) => a.sales > b.sales ? a : b)
      assert.ok(["06", "07", "08"].includes(peak.month.slice(5)), `peak month ${peak.month}`)
    }
    for (const row of source.weekend_vs_weekday) {
      // Real insight: weekends sell more than weekdays
      assert.ok(row.weekend_avg > row.weekday_avg, `Store ${row.store}: weekend not > weekday`)
      const uplift = (row.weekend_avg / row.weekday_avg - 1) * 100
      // Sanity range 10-80%: real data ~45%, mock ~30%. Catches sign-flipped bugs.
      assert.ok(uplift >= 10 && uplift <= 80, `Store ${row.store}: uplift ${uplift.toFixed(1)}% out of 10-80% range`)
    }
  }
})

test("store filtering updates all charts without mutating cached data", async () => {
  const data = await getEda()
  const before = structuredClone(data)
  const all = selectEda(data, "all")
  assert.strictEqual(all.monthly, data.monthly_total)
  assert.equal(all.weekend.length, 5)
  assert.equal(all.weekly.length, 7)
  // uplift is positive and in a sane range (real data ~45%)
  assert.ok(all.uplift !== null && all.uplift > 10 && all.uplift <= 80,
    `all-store uplift ${all.uplift} out of range`)
  for (const store of [1, 2, 3, 4, 5]) {
    const view = selectEda(data, store)
    assert.strictEqual(view.monthly, data.by_store![store].monthly_total)
    assert.strictEqual(view.heatmap, data.by_store![store].month_year_heatmap)
    assert.equal(view.weekend.length, 1)
    assert.equal(view.weekend[0].store, store)
    assert.deepEqual(view.weekly.map(row => row.avg_sales), data.weekday_avg.filter(row => row.store === store).map(row => row.avg_sales))
    assert.notDeepEqual(view.monthly, all.monthly)
  }
  assert.deepEqual(data, before)
})

test("EDA empty data and optional breakdowns never display fabricated store totals", () => {
  const empty = selectEda({ monthly_total: [], weekday_avg: [], weekend_vs_weekday: [] }, "all")
  assert.deepEqual(empty, { monthly: [], weekly: [], weekend: [], heatmap: [], uplift: null })
  const noBreakdown = selectEda({ monthly_total: [{ month: "2013-01", sales: 100 }], weekday_avg: [], weekend_vs_weekday: [] }, 1)
  assert.deepEqual(noBreakdown.monthly, [])
  assert.deepEqual(noBreakdown.heatmap, [])
})

test("quality counts reflect the selected store and include leap day", () => {
  assert.deepEqual(edaQuality("all"), { rows: 456500, series: 250, missing: 0, duplicates: 0 })
  assert.deepEqual(edaQuality(3), { rows: 91300, series: 50, missing: 0, duplicates: 0 })
})
