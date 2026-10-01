import type { BaselinePoint, ErrorMetrics, Point } from "@/lib/types"

export const mean = (values: number[]) => values.reduce((sum, value) => sum + value, 0) / values.length
export const round = (value: number) => Math.round(value * 100) / 100
export const standardDeviation = (values: number[]) => Math.sqrt(mean(values.map(value => (value - mean(values)) ** 2)))

export function seededRandom(key: string) {
  let seed = 2166136261
  for (const char of key) seed = Math.imul(seed ^ char.charCodeAt(0), 16777619)
  return () => {
    let value = seed += 0x6d2b79f5
    value = Math.imul(value ^ (value >>> 15), value | 1)
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61)
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296
  }
}

export function dates(start: string, count: number) {
  const time = Date.parse(`${start}T00:00:00Z`)
  return Array.from({ length: count }, (_, i) => new Date(time + i * 86_400_000).toISOString().slice(0, 10))
}

export function expectedDemand(ds: string, base: number) {
  const date = new Date(`${ds}T00:00:00Z`)
  const year = date.getUTCFullYear()
  const dayOfYear = (date.getTime() - Date.UTC(year, 0, 1)) / 86_400_000
  const trend = 1.08 ** (year - 2017 + dayOfYear / 365)
  const yearly = 1 + 0.22 * Math.cos(2 * Math.PI * (dayOfYear - 195) / 365)
  const weekly = [1.22, 0.99, 0.94, 0.94, 1, 1.06, 1.22][date.getUTCDay()]
  return base * trend * yearly * weekly
}

export function measureErrors(actual: Point[], forecast: BaselinePoint[]): ErrorMetrics {
  const errors = actual.map((point, i) => point.y - forecast[i].yhat)
  return { mape: mean(errors.map((error, i) => Math.abs(error) / actual[i].y)) * 100, rmse: Math.sqrt(mean(errors.map(error => error ** 2))) }
}

// Calibrate synthetic deviations, not displayed metrics: all reported errors are measured from the points.
export function calibrateActual(raw: Point[], baseline: number, targetMape: number): Point[] {
  const flat = raw.map(({ ds }) => ({ ds, yhat: baseline }))
  const scaled = (scale: number) => raw.map(({ ds, y }) => ({ ds, y: Math.max(1, baseline + (y - baseline) * scale) }))
  let low = 0
  let high = 8
  for (let i = 0; i < 32; i++) {
    const mid = (low + high) / 2
    if (measureErrors(scaled(mid), flat).mape < targetMape) low = mid
    else high = mid
  }
  return scaled((low + high) / 2).map(point => ({ ...point, y: round(point.y) }))
}
