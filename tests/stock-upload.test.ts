import assert from "node:assert/strict"
import { test } from "node:test"
import { getRestockInputs } from "../lib/data"
import { defaultRestockOptions } from "../lib/restock-view"
import { computeRestock } from "../lib/restock"
import {
  applyUploadedStock,
  MAX_STOCK_CSV_BYTES,
  parseStockCsv,
  stockNoteText,
  stockTemplateCsv,
} from "../lib/stock-upload"

test("stock CSV accepts case-insensitive trimmed headers and valid rows", () => {
  const result = parseStockCsv(" STORE , Item , CURRENT_STOCK \r\n1,12,100.5\r\n5,50,0\r\n")
  assert.deepEqual(result, {
    ok: true,
    rows: { S1_I12: 100.5, S5_I50: 0 },
    count: 2,
  })
})

test("stock CSV reports missing headers and invalid store or negative stock with source lines", () => {
  const missing = parseStockCsv("store,item\n1,12\n")
  assert.equal(missing.ok, false)
  if (missing.ok === false) assert.deepEqual(missing.errors, [{ line: 1, message: "Missing 'current_stock' column" }])

  const invalid = parseStockCsv("store,item,current_stock\n6,12,10\n1,13,-2\n")
  assert.equal(invalid.ok, false)
  if (invalid.ok === false) {
    assert.deepEqual(invalid.errors, [
      { line: 2, message: "store must be 1-5, got 6" },
      { line: 3, message: "'current_stock' must be a finite number >= 0" },
    ])
  }
})

test("stock CSV rejects duplicate pairs", () => {
  const result = parseStockCsv("store,item,current_stock\n1,12,100\n1,12,120\n")
  assert.equal(result.ok, false)
  if (result.ok === false) {
    assert.deepEqual(result.errors, [{ line: 3, message: "Duplicate (store, item): (1, 12)" }])
  }
})

test("stock CSV enforces the 250-row and 1 MB limits", () => {
  const dataRows = Array.from({ length: 251 }, (_, index) =>
    index < 250
      ? `${Math.floor(index / 50) + 1},${index % 50 + 1},${index}`
      : "1,1,999",
  ).join("\n")
  const tooMany = parseStockCsv(`store,item,current_stock\n${dataRows}`)
  assert.equal(tooMany.ok, false)
  if (tooMany.ok === false) assert.ok(tooMany.errors.some(error => error.line === 252 && error.message.includes("at most 250")))

  const oversized = parseStockCsv("x".repeat(MAX_STOCK_CSV_BYTES + 1))
  assert.equal(oversized.ok, false)
  if (oversized.ok === false) assert.deepEqual(oversized.errors, [{ line: 0, message: "CSV file must be 1 MB or smaller" }])
})

test("stock CSV caps reported errors at 20 while retaining line numbers", () => {
  const rows = Array.from({ length: 25 }, (_, index) => `9,${index + 1},-1`).join("\n")
  const result = parseStockCsv(`store,item,current_stock\n${rows}`)
  assert.equal(result.ok, false)
  if (result.ok === false) {
    assert.equal(result.errors.length, 20)
    assert.equal(result.errors[0].line, 2)
    assert.equal(result.errors[19].line, 11)
  }
})

test("stock template contains all 250 products and round-trips through the parser", async () => {
  const inputs = await getRestockInputs()
  const csv = stockTemplateCsv(inputs)
  const result = parseStockCsv(csv)
  assert.equal(result.ok, true)
  if (result.ok === true) {
    assert.equal(result.count, 250)
    assert.equal(result.rows.S1_I12, inputs.S1_I12.current_stock)
  }
})

test("uploaded stock changes client restock totals and leaves missing series simulated", async () => {
  const inputs = await getRestockInputs()
  const base = computeRestock(inputs, defaultRestockOptions)
  const doubled = applyUploadedStock(inputs, { S1_I1: inputs.S1_I1.current_stock * 2 })
  const updated = computeRestock(doubled, defaultRestockOptions)
  assert.equal(doubled.S1_I1.current_stock, inputs.S1_I1.current_stock * 2)
  assert.strictEqual(doubled.S1_I2, inputs.S1_I2)
  assert.notEqual(
    updated.reduce((sum, row) => sum + row.restock_qty, 0),
    base.reduce((sum, row) => sum + row.restock_qty, 0),
  )
})

test("stock note switches between simulated and uploaded stock", () => {
  assert.equal(stockNoteText(false, 0), "Stock levels are simulated (dataset has no inventory data)")
  assert.equal(stockNoteText(true, 12), "Using uploaded stock for 12 series (others simulated)")
})
