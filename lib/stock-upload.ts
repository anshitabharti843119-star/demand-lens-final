import type { RestockInput } from "@/lib/types"

export const MAX_STOCK_CSV_BYTES = 1024 * 1024

export interface StockUploadError {
  line: number
  message: string
}

export interface StockUploadResult {
  ok: true
  rows: Record<string, number>
  count: number
}

export interface StockUploadFailure {
  ok: false
  errors: StockUploadError[]
}

export interface SavedStockUpload {
  uploaded_at: string
  source_filename: string
  rows: Record<string, number>
  row_count: number
}

type CsvRecord = { cells: string[]; line: number }

function parseRecords(text: string): { records: CsvRecord[]; error?: StockUploadError } {
  const records: CsvRecord[] = []
  let cells: string[] = []
  let field = ""
  let inQuotes = false
  let closedQuote = false
  let line = 1
  let recordLine = 1

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index]
    if (inQuotes) {
      if (character === '"') {
        if (text[index + 1] === '"') {
          field += '"'
          index += 1
        } else {
          inQuotes = false
          closedQuote = true
        }
      } else {
        field += character
        if (character === "\n") line += 1
      }
      continue
    }

    if (character === "," ) {
      cells.push(field)
      field = ""
      closedQuote = false
    } else if (character === "\r" || character === "\n") {
      cells.push(field)
      if (cells.some(value => value.trim())) records.push({ cells, line: recordLine })
      cells = []
      field = ""
      closedQuote = false
      if (character === "\r" && text[index + 1] === "\n") index += 1
      line += 1
      recordLine = line
    } else if (character === '"' && field.length === 0 && !closedQuote) {
      inQuotes = true
    } else if (closedQuote && character.trim() !== "") {
      return { records, error: { line, message: "Invalid CSV: unexpected character after closing quote" } }
    } else {
      field += character
    }
  }

  if (inQuotes) return { records, error: { line: recordLine, message: "Invalid CSV: unterminated quoted field" } }
  cells.push(field)
  if (cells.some(value => value.trim())) records.push({ cells, line: recordLine })
  return { records }
}

export function parseStockCsv(text: string): StockUploadResult | StockUploadFailure {
  if (new TextEncoder().encode(text).byteLength > MAX_STOCK_CSV_BYTES) {
    return { ok: false, errors: [{ line: 0, message: "CSV file must be 1 MB or smaller" }] }
  }
  if (!text.trim()) return { ok: false, errors: [{ line: 0, message: "Empty file" }] }

  const parsed = parseRecords(text)
  if (parsed.error) return { ok: false, errors: [parsed.error] }
  const [header, ...records] = parsed.records
  if (!header) return { ok: false, errors: [{ line: 1, message: "Missing or invalid CSV header" }] }

  const normalizedHeader = header.cells.map(value => value.trim().replace(/^\uFEFF/, "").toLowerCase())
  const required = ["store", "item", "current_stock"] as const
  const indexes = new Map<string, number>()
  for (const name of required) {
    const index = normalizedHeader.indexOf(name)
    if (index >= 0) indexes.set(name, index)
  }
  const headerErrors = required
    .filter(name => !indexes.has(name))
    .map(name => ({ line: 1, message: `Missing '${name}' column` }))
  if (headerErrors.length) return { ok: false, errors: headerErrors.slice(0, 20) }

  const rows: Record<string, number> = {}
  const errors: StockUploadError[] = []
  const seenPairs = new Set<string>()
  let dataRows = 0

  for (const record of records) {
    dataRows += 1
    const rowErrors: string[] = []
    if (dataRows > 250) rowErrors.push("CSV may contain at most 250 data rows")
    const storeIndex = indexes.get("store")!
    const itemIndex = indexes.get("item")!
    const stockIndex = indexes.get("current_stock")!
    const missing = [
      ...(storeIndex >= record.cells.length ? ["store"] : []),
      ...(itemIndex >= record.cells.length ? ["item"] : []),
      ...(stockIndex >= record.cells.length ? ["current_stock"] : []),
    ]
    if (missing.length) {
      errors.push({ line: record.line, message: `Missing value(s) for ${missing.join(", ")}` })
      continue
    }

    const storeValue = record.cells[storeIndex].trim()
    const itemValue = record.cells[itemIndex].trim()
    const stockValue = record.cells[stockIndex].trim()
    const store = /^[+-]?\d+$/.test(storeValue) ? Number(storeValue) : Number.NaN
    const item = /^[+-]?\d+$/.test(itemValue) ? Number(itemValue) : Number.NaN
    const numericStock = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(stockValue)
    const stock = numericStock ? Number(stockValue) : Number.NaN

    if (!Number.isInteger(store)) rowErrors.push(`store must be an integer, got '${storeValue}'`)
    else if (store < 1 || store > 5) rowErrors.push(`store must be 1-5, got ${store}`)
    if (!Number.isInteger(item)) rowErrors.push(`item must be an integer, got '${itemValue}'`)
    else if (item < 1 || item > 50) rowErrors.push(`item must be 1-50, got ${item}`)
    if (!Number.isFinite(stock)) rowErrors.push(`'current_stock' must be numeric, got '${stockValue}'`)
    else if (stock < 0) rowErrors.push("'current_stock' must be a finite number >= 0")

    if (Number.isInteger(store) && Number.isInteger(item)) {
      const pair = `${store}:${item}`
      if (seenPairs.has(pair)) rowErrors.push(`Duplicate (store, item): (${store}, ${item})`)
      else seenPairs.add(pair)
    }

    if (rowErrors.length) {
      for (const message of rowErrors) errors.push({ line: record.line, message })
    } else {
      rows[`S${store}_I${item}`] = stock
    }
  }

  if (errors.length) return { ok: false, errors: errors.slice(0, 20) }
  return { ok: true, rows, count: Object.keys(rows).length }
}

export function applyUploadedStock(
  inputs: Record<string, RestockInput>,
  uploadedRows: Record<string, number>,
): Record<string, RestockInput> {
  return Object.fromEntries(
    Object.entries(inputs).map(([seriesId, input]) => [
      seriesId,
      Object.hasOwn(uploadedRows, seriesId) ? { ...input, current_stock: uploadedRows[seriesId] } : input,
    ]),
  )
}

export function stockTemplateCsv(inputs: Record<string, RestockInput>): string {
  const lines = [["store", "item", "current_stock"].join(",")]
  const sorted = Object.entries(inputs).sort(([, left], [, right]) => left.store - right.store || left.item - right.item)
  for (const [, input] of sorted) lines.push(`${input.store},${input.item},${input.current_stock}`)
  return `${lines.join("\r\n")}\r\n`
}

const STOCK_STORAGE_KEY = "demandlens:stock:v1"

export function loadSavedStockUpload(): SavedStockUpload | null {
  try {
    const serialized = window.localStorage.getItem(STOCK_STORAGE_KEY)
    if (!serialized) return null
    const value: unknown = JSON.parse(serialized)
    if (!value || typeof value !== "object") return null
    const candidate = value as Partial<SavedStockUpload>
    if (
      typeof candidate.uploaded_at !== "string" ||
      typeof candidate.source_filename !== "string" ||
      typeof candidate.row_count !== "number" ||
      !Number.isInteger(candidate.row_count) ||
      candidate.row_count < 0 ||
      candidate.row_count > 250 ||
      !candidate.rows ||
      typeof candidate.rows !== "object" ||
      Array.isArray(candidate.rows)
    ) return null
    const rows = candidate.rows as Record<string, unknown>
    if (
      Object.keys(rows).length !== candidate.row_count ||
      !Object.entries(rows).every(([seriesId, stock]) =>
        /^S[1-5]_I(?:[1-9]|[1-4][0-9]|50)$/.test(seriesId) &&
        typeof stock === "number" &&
        Number.isFinite(stock) &&
        stock >= 0,
      )
    ) return null
    return { ...candidate, rows: rows as Record<string, number> } as SavedStockUpload
  } catch {
    return null
  }
}

export function saveStockUpload(upload: SavedStockUpload): boolean {
  try {
    window.localStorage.setItem(STOCK_STORAGE_KEY, JSON.stringify(upload))
    return true
  } catch {
    return false
  }
}

export function clearSavedStockUpload(): void {
  try {
    window.localStorage.removeItem(STOCK_STORAGE_KEY)
  } catch {
    // The in-memory state is still cleared when browser storage is unavailable.
  }
}

export function stockNoteText(usingUploadedStock: boolean, uploadedCount: number): string {
  return usingUploadedStock && uploadedCount > 0
    ? `Using uploaded stock for ${uploadedCount} series (others simulated)`
    : "Stock levels are simulated (dataset has no inventory data)"
}
