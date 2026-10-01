import { test } from "node:test"
import assert from "node:assert/strict"
import { getRestockInputs } from "../lib/data"
import { computeRestock } from "../lib/restock"
import { defaultRestockOptions, defaultRestockFilters, defaultRestockSort, filterSortRestock, summarizeRestock, restockCsv, formatUnits, formatCover } from "../lib/restock-view"

test("restock view filters positive orders by store, priority and item without mutating computed rows", async () => {
  const computed = computeRestock(await getRestockInputs(), defaultRestockOptions)
  const original = [...computed]
  const rows = filterSortRestock(computed, defaultRestockFilters, defaultRestockSort)
  assert.ok(rows.length > 25)
  assert.ok(rows.every(row => row.restock_qty > 0))
  assert.ok(rows.every((row, index) => !index || row.days_of_cover >= rows[index - 1].days_of_cover))
  assert.deepEqual(computed, original)
  const target = rows[0]
  const filtered = filterSortRestock(computed, { store: String(target.store), priority: target.priority, search: `Item ${target.item}` }, defaultRestockSort)
  assert.ok(filtered.includes(target))
  assert.ok(filtered.every(row => row.store === target.store && row.priority === target.priority && String(row.item).includes(String(target.item))))
  assert.deepEqual(filterSortRestock(computed, { ...defaultRestockFilters, search: "999" }, defaultRestockSort), [])
})

test("every numeric column sorts numerically, priorities sort by urgency, summary covers all filtered rows", async () => {
  const computed = computeRestock(await getRestockInputs(), defaultRestockOptions)
  for (const key of ["item", "store", "current_stock", "forecast_demand", "safety_stock", "restock_qty", "days_of_cover"] as const) {
    for (const direction of ["asc", "desc"] as const) {
      const rows = filterSortRestock(computed, defaultRestockFilters, { key, direction })
      assert.ok(rows.every((row, i) => !i || (direction === "asc" ? row[key] >= rows[i - 1][key] : row[key] <= rows[i - 1][key])))
    }
  }
  const rows = filterSortRestock(computed, defaultRestockFilters, { key: "priority", direction: "asc" })
  const rank = { HIGH: 0, MEDIUM: 1, LOW: 2 }
  assert.ok(rows.every((row, i) => !i || rank[row.priority] >= rank[rows[i - 1].priority]))
  assert.deepEqual(summarizeRestock(rows), { products: rows.length, units: rows.reduce((sum, row) => sum + row.restock_qty, 0), high: rows.filter(row => row.priority === "HIGH").length, cover: rows.reduce((sum, row) => sum + row.days_of_cover, 0) / rows.length })
  assert.deepEqual(summarizeRestock([]), { products: 0, units: 0, high: 0, cover: 0 })
})

test("CSV includes every filtered row in display order with identical displayed numbers", async () => {
  const computed = computeRestock(await getRestockInputs(), { ...defaultRestockOptions, stockMultiplier: 0.7, horizon: 14 })
  const rows = filterSortRestock(computed, { ...defaultRestockFilters, store: "2" }, { key: "restock_qty", direction: "desc" })
  const lines = restockCsv(rows, 14).trim().split("\r\n")
  assert.equal(lines.length, rows.length + 1)
  assert.ok(lines[0].includes("Forecast demand (14 days)"))
  rows.forEach((row, i) => assert.deepEqual(lines[i + 1].slice(1, -1).split('\",\"'), [`Item ${row.item}`, `Store ${row.store}`, formatUnits(row.current_stock), formatUnits(row.forecast_demand), formatUnits(row.safety_stock), formatUnits(row.restock_qty), formatCover(row.days_of_cover), row.priority]))
  assert.equal(restockCsv([], 30).trim().split("\r\n").length, 1)
})

test("changing either slider preserves exact row references between list and sheet and updates summaries", async () => {
  const inputs = await getRestockInputs()
  const base = computeRestock(inputs, defaultRestockOptions)
  for (const patch of [{ leadTime: 14 }, { stockMultiplier: 0.5 }, { stockMultiplier: 2 }]) {
    const computed = computeRestock(inputs, { ...defaultRestockOptions, ...patch })
    const rows = filterSortRestock(computed, defaultRestockFilters, defaultRestockSort)
    for (const row of rows) {
      assert.equal(computed.find(candidate => candidate.series_id === row.series_id), row)
      assert.equal(row.restock_qty, Math.max(0, Math.ceil(row.forecast_demand + row.safety_stock - row.current_stock)))
    }
    assert.notEqual(summarizeRestock(rows).units, summarizeRestock(base.filter(row => row.restock_qty > 0)).units)
  }
})
