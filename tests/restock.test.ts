import { test } from "node:test"
import assert from "node:assert/strict"
import { computeRestock, type RestockOptions } from "../lib/restock"
import { getRestockInputs } from "../lib/data"
import type { RestockInput } from "../lib/types"

const input: RestockInput = { store: 1, item: 1, current_stock: 20, avg_daily_28: 10, sigma_daily: 2, yhat_future: Array(30).fill(10) }
const options: RestockOptions = { horizon: 14, serviceLevel: 0.95, leadTime: 4, stockMultiplier: 1 }

test("restock formulas match a hand-calculated fixture and do not mutate inputs", () => {
  const snapshot = structuredClone(input)
  const [row] = computeRestock({ S1_I1: input }, options)
  assert.equal(row.forecast_demand, 140)
  assert.equal(row.safety_stock, 6.6)
  assert.equal(row.current_stock, 20)
  assert.equal(row.restock_qty, 127)
  assert.equal(row.days_of_cover, 2)
  assert.equal(row.priority, "HIGH")
  assert.deepEqual(input, snapshot)
})

test("horizon, stock multiplier and all service levels change results correctly", () => {
  for (const [serviceLevel, z] of [[0.9, 1.28], [0.95, 1.65], [0.99, 2.33]] as const) {
    const [row] = computeRestock({ S1_I1: input }, { ...options, horizon: 30, stockMultiplier: 2, serviceLevel })
    assert.equal(row.forecast_demand, 300)
    assert.equal(row.safety_stock, z * 2 * Math.sqrt(4))
    assert.equal(row.current_stock, 40)
    assert.equal(row.days_of_cover, 4)
    assert.equal(row.priority, "MEDIUM")
  }
})

test("priority boundaries, no-restock rows, sorting and empty input", () => {
  const rows = computeRestock({ enough: { ...input, current_stock: 300 }, medium: { ...input, current_stock: 40 }, high: input, boundary: { ...input, current_stock: 140 } }, options)
  assert.deepEqual(rows.map(row => row.series_id), ["high", "medium", "boundary", "enough"])
  assert.equal(rows[1].priority, "MEDIUM")
  assert.equal(rows[2].priority, "LOW")
  assert.equal(rows[3].restock_qty, 0)
  assert.equal(rows.filter(row => row.restock_qty > 0).length, 3)
  assert.deepEqual(computeRestock({}, options), [])
})

test("zero demand has infinite cover and invalid inputs are rejected", () => {
  const [row] = computeRestock({ zero: { ...input, yhat_future: Array(30).fill(0), sigma_daily: 0 } }, options)
  assert.equal(row.days_of_cover, Infinity)
  assert.equal(row.restock_qty, 0)
  assert.equal(row.priority, "LOW")
  assert.throws(() => computeRestock({ invalid: { ...input, yhat_future: [1] } }, options), RangeError)
  assert.throws(() => computeRestock({ invalid: { ...input, current_stock: -1 } }, options), RangeError)
  assert.throws(() => computeRestock({ invalid: { ...input, sigma_daily: NaN } }, options), RangeError)
  assert.throws(() => computeRestock({}, { ...options, leadTime: 0 }), RangeError)
  assert.throws(() => computeRestock({}, { ...options, stockMultiplier: -1 }), RangeError)
})

test("full mock restock list is sorted and has useful priority variation", async () => {
  const rows = computeRestock(await getRestockInputs(), { ...options, horizon: 30, leadTime: 3 })
  assert.equal(rows.length, 250)
  assert.ok(rows.some(row => row.priority === "HIGH"))
  assert.ok(rows.some(row => row.priority === "MEDIUM"))
  assert.ok(rows.some(row => row.priority === "LOW"))
  assert.ok(rows.some(row => row.restock_qty === 0))
  assert.ok(rows.every((row, i) => i === 0 || row.days_of_cover >= rows[i - 1].days_of_cover))
})
