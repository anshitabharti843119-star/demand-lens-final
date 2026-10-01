/** Backend API client with fallback to static JSON when backend is offline. */

import type { ForecastPoint, Point, Horizon, ErrorMetrics, RestockRow } from "@/lib/types"

export type { ForecastPoint, Point, Horizon, ErrorMetrics, RestockRow }

// Configuration: backend URL from env, default to localhost
const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "")

// Timeout constants (in seconds)
const DEFAULT_TIMEOUT = 5
const REFIT_TIMEOUT = 100

export interface ApiValidationError {
  line?: number
  message: string
}

export interface ApiError {
  ok: false
  error: string
  status?: number
  errors?: ApiValidationError[]
}

export interface ApiSuccess<T> {
  ok: true
  data: T
}

export type ApiResponse<T> = ApiSuccess<T> | ApiError

// ── Generic API call helper ──────────────────────────────────────────────────

function validationErrors(value: unknown): ApiValidationError[] | undefined {
  if (!Array.isArray(value)) return undefined
  return value.flatMap((entry: unknown) => {
    if (!entry || typeof entry !== "object" || !("message" in entry)) return []
    const { line, message } = entry as { line?: unknown; message: unknown }
    if (typeof message !== "string") return []
    return [{ ...(typeof line === "number" ? { line } : {}), message }]
  })
}

async function apiCall<T>(
  path: string,
  options?: RequestInit,
  timeoutSeconds: number = DEFAULT_TIMEOUT,
): Promise<ApiResponse<T>> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutSeconds * 1000)

  try {
    const headers = new Headers(options?.headers)
    if (options?.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json")
    }
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers,
    })

    if (!response.ok) {
      let message = `HTTP ${response.status}`
      let errors: ApiValidationError[] | undefined
      try {
        const errorData: unknown = await response.json()
        if (errorData && typeof errorData === "object") {
          const payload = errorData as {
            detail?: unknown
            message?: unknown
            error?: unknown
            errors?: unknown
          }
          errors = validationErrors(payload.errors)
          if (typeof payload.detail === "string") message = payload.detail
          else if (typeof payload.error === "string") message = payload.error
          else if (typeof payload.message === "string") message = payload.message
          else if (errors?.length) {
            message = errors.map(item => item.line ? `Line ${item.line}: ${item.message}` : item.message).join("; ")
          }
        }
      } catch {
        // Ignore JSON parse errors
      }
      return { ok: false, error: message, status: response.status, ...(errors ? { errors } : {}) }
    }

    return { ok: true, data: await response.json() as T }
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return { ok: false, error: `Request timed out after ${timeoutSeconds} seconds` }
    }

    // Network error or other exception
    return { ok: false, error: error instanceof Error ? error.message : "Unknown error" }
  } finally {
    clearTimeout(timeoutId)
  }
}

// ── Health check ─────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string
  series_count: number
  data_dir: string
  prophet_available: boolean
  version: string
}

export async function health(): Promise<ApiResponse<HealthResponse>> {
  return apiCall<HealthResponse>("/api/health")
}

// ── Forecast refit ───────────────────────────────────────────────────────────

export interface RefitRequest {
  series_id: string
  train_end: string  // ISO date
  horizon: number
}

export interface RefitResponse {
  series_id: string
  train_end: string
  horizon: number
  forecast: ForecastPoint[]
  actual: Point[]
  metrics: {
    model: ErrorMetrics
    baseline: ErrorMetrics
  } | null
  fit_seconds: number
  cached: boolean
  params: Record<string, unknown>
}

export async function refit(request: RefitRequest): Promise<ApiResponse<RefitResponse>> {
  return apiCall<RefitResponse>("/api/forecast/refit", {
    method: "POST",
    body: JSON.stringify(request),
  }, REFIT_TIMEOUT)
}

// ── What-if scenario ─────────────────────────────────────────────────────────

export interface WhatIfScenario {
  demand_uplift_pct: number
  start_day: number
  end_day: number
}

export interface WhatIfOptions {
  horizon: number
  service_level: number
  lead_time: number
  stock_multiplier: number
  store?: number
  priority?: "HIGH" | "MEDIUM" | "LOW"
  only_restock?: boolean
  use_uploaded_stock?: boolean
}

export interface WhatIfChange {
  series_id: string
  qty_before: number
  qty_after: number
  priority_before: "HIGH" | "MEDIUM" | "LOW"
  priority_after: "HIGH" | "MEDIUM" | "LOW"
}

export interface RestockSummary {
  total_products: number
  total_units: number
  high_priority: number
  avg_days_of_cover: number
}

export interface WhatIfResponse {
  baseline: { rows: RestockRow[]; summary: RestockSummary }
  scenario: { rows: RestockRow[]; summary: RestockSummary }
  delta: { total_units_change: number; products_changing_priority: number; top_changes: WhatIfChange[] }
  disclaimer: string
  stock_source?: string
}

export async function whatif(request: {
  scenario: WhatIfScenario
  options: WhatIfOptions
  series_id?: string
}): Promise<ApiResponse<WhatIfResponse>> {
  return apiCall<WhatIfResponse>("/api/whatif", {
    method: "POST",
    body: JSON.stringify(request),
  })
}

// ── Stock upload ─────────────────────────────────────────────────────────────

export interface StockUploadResponse {
  accepted_rows: number
  missing_series_count: number
  uploaded_at: string
}

export async function uploadStock(file: File): Promise<ApiResponse<StockUploadResponse>> {
  const formData = new FormData()
  formData.append("file", file)

  return apiCall<StockUploadResponse>("/api/stock/upload", {
    method: "POST",
    body: formData,
  })
}

// ── Stock state ──────────────────────────────────────────────────────────────

export interface StockState {
  active: boolean
  uploaded_at?: string
  source_filename?: string
  row_count?: number
}

export async function getStock(): Promise<ApiResponse<StockState>> {
  return apiCall<StockState>("/api/stock")
}

export async function clearStock(): Promise<ApiResponse<{ message: string }>> {
  return apiCall<{ message: string }>("/api/stock", { method: "DELETE" })
}

export function stockTemplateUrl(): string {
  return `${API_BASE_URL}/api/stock/template`
}

// ── Restock with uploaded stock ──────────────────────────────────────────────

export interface RestockRequest {
  horizon: number
  service_level: number
  lead_time: number
  stock_multiplier: number
  store?: number
  priority?: "HIGH" | "MEDIUM" | "LOW"
  only_restock?: boolean
  use_uploaded_stock?: boolean
}

export interface RestockResponse {
  rows: RestockRow[]
  summary: RestockSummary
  stock_source?: string
}

export async function restock(request: RestockRequest): Promise<ApiResponse<RestockResponse>> {
  return apiCall<RestockResponse>("/api/restock", {
    method: "POST",
    body: JSON.stringify(request),
  })
}
