import type { EdaData, PortfolioRow, RestockInput, SeriesData } from "@/lib/types"

// ─── environment detection ────────────────────────────────────────────────────
// Browser  → fetch('/data/…')
// Node.js  → fs.readFileSync from public/data/ (used by `npm test`)

const IS_BROWSER = typeof window !== "undefined"

const SCHEMA_VERSION = 1

async function readJson<T>(path: string): Promise<T> {
  if (IS_BROWSER) {
    const res = await fetch(`/data/${path}`)
    if (!res.ok) throw new Error(`Failed to load /data/${path} (HTTP ${res.status})`)
    const data = await res.json() as T
    checkSchemaVersion(data)
    return data
  }
  // Node.js (test runner)
  const fs  = await import("fs")
  const mod = await import("path")
  const abs = mod.join(process.cwd(), "public", "data", path)
  try {
    const data = JSON.parse(fs.readFileSync(abs, "utf-8")) as T
    checkSchemaVersion(data)
    return data
  } catch (e) {
    throw new Error(`Failed to load ${path}: ${e instanceof Error ? e.message : String(e)}`)
  }
}

function checkSchemaVersion(data: unknown): void {
  if (data && typeof data === "object" && "schema_version" in data) {
    const version = (data as { schema_version: unknown }).schema_version
    if (version !== SCHEMA_VERSION) {
      console.warn(
        `[DemandLens] schema_version mismatch: expected ${SCHEMA_VERSION}, got ${version}. ` +
        `Data may be from a different pipeline version.`
      )
    }
  }
}

// ─── manifest ─────────────────────────────────────────────────────────────────
type Manifest = {
  stores: number[]
  items: number[]
  series_ids: string[]
  train_end: string
  test_start: string
  test_end: string
  future_end: string
}

let manifestCache: Manifest | undefined

export async function getManifest(): Promise<Manifest> {
  if (manifestCache) return manifestCache
  manifestCache = await readJson<Manifest>("manifest.json")
  return manifestCache
}

// ─── series ───────────────────────────────────────────────────────────────────
const seriesCache = new Map<string, SeriesData>()

// Validate series_id format (must be S1-5_I1-50)
function validateSeriesId(seriesId: string): { store: number; item: number } {
  const match = /^S([1-5])_I([1-9]|[1-4][0-9]|50)$/.exec(seriesId)
  if (!match) throw new Error(`Invalid series ID: ${seriesId}`)
  return { store: Number(match[1]), item: Number(match[2]) }
}

export async function getSeries(seriesId: string): Promise<SeriesData> {
  validateSeriesId(seriesId) // throws for out-of-range IDs

  const cached = seriesCache.get(seriesId)
  if (cached) return cached

  const series = await readJson<SeriesData>(`series/${seriesId}.json`)
  seriesCache.set(seriesId, series)
  return series
}

// ─── restock inputs ───────────────────────────────────────────────────────────
let restockCache: Record<string, RestockInput> | undefined

export async function getRestockInputs(): Promise<Record<string, RestockInput>> {
  if (restockCache) return restockCache
  restockCache = await readJson<Record<string, RestockInput>>("restock_inputs.json")
  return restockCache
}

// ─── portfolio ────────────────────────────────────────────────────────────────
let portfolioCache: PortfolioRow[] | undefined

export async function getPortfolio(): Promise<PortfolioRow[]> {
  if (portfolioCache) return portfolioCache
  portfolioCache = await readJson<PortfolioRow[]>("portfolio.json")
  return portfolioCache
}

// ─── EDA ──────────────────────────────────────────────────────────────────────
let edaCache: EdaData | undefined

export async function getEda(): Promise<EdaData> {
  if (edaCache) return edaCache
  edaCache = await readJson<EdaData>("eda.json")
  return edaCache
}
