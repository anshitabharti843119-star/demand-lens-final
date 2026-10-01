"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import useSWR from "swr"
import { getSeries, getPortfolio } from "@/lib/data"
import { readSelection } from "@/lib/selection"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { ForecastMetrics } from "./forecast-metrics"
import { ForecastChart } from "./forecast-chart"
import { RestockPreview } from "./restock-preview"
import { useBackendStatus } from "@/hooks/useBackendStatus"
import { refit, type RefitResponse } from "@/lib/api"

export function ForecastSkeleton() {
  return <div className="flex flex-col gap-6" role="status" aria-label="Loading forecast"><div className="grid grid-cols-2 gap-4 xl:grid-cols-6"><Skeleton className="col-span-2 h-44" />{[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-44" />)}</div><Skeleton className="h-[520px] w-full" /></div>
}

/** Returns the best series to illustrate "model helped least" or a real baseline win. */
function useLeastHelpfulSeries(horizon: number) {
  const { data: portfolio } = useSWR("portfolio", getPortfolio, { revalidateOnFocus: false })
  if (!portfolio) return null
  // Prefer a genuine baseline win; fall back to lowest improvement_pct
  const baselineWin = portfolio.find(r => r.winner === "baseline")
  const target = baselineWin ?? [...portfolio].sort((a, b) => a.improvement_pct - b.improvement_pct)[0]
  if (!target) return null
  return {
    href: `/forecast?store=${target.store}&item=${target.item}&h=${horizon}&mode=backtest`,
    label: baselineWin ? "Try a series where baseline wins" : "Try the series where the model helped least",
  }
}

export function ForecastDashboard() {
  const params = useSearchParams()
  const { store, item, horizon, mode } = readSelection(params)
  const { data, error, mutate, isValidating } = useSWR(`S${store}_I${item}`, getSeries, {
    keepPreviousData: true, revalidateOnFocus: false,
    onSuccess: series => {
      const prefetch = () => { for (const neighbor of [series.item - 1, series.item + 1]) if (neighbor >= 1 && neighbor <= 50) void getSeries(`S${series.store}_I${neighbor}`).catch(() => {}) }
      if (typeof window.requestIdleCallback === "function") window.requestIdleCallback(prefetch)
      else window.setTimeout(prefetch, 150)
    },
  })
  const leastHelpful = useLeastHelpfulSeries(horizon)
  
  // Backend status
  const { backendOnline } = useBackendStatus()
  
  // Refit state
  const [refitLoading, setRefitLoading] = useState(false)
  const [refitElapsed, setRefitElapsed] = useState(0)
  const [trainEnd, setTrainEnd] = useState("2017-11-30")
  const [refitHorizon, setRefitHorizon] = useState<14 | 30>(horizon)
  const [refitResponse, setRefitResponse] = useState<RefitResponse | null>(null)
  const [refitError, setRefitError] = useState<string | null>(null)

  useEffect(() => {
    if (!refitLoading) return
    const timer = window.setInterval(() => setRefitElapsed(value => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [refitLoading])
  
  const handleRefit = async () => {
    if (!backendOnline) return
    setRefitLoading(true)
    setRefitElapsed(0)
    setRefitError(null)
    setRefitResponse(null)
    const result = await refit({
      series_id: `S${store}_I${item}`,
      train_end: trainEnd,
      horizon: refitHorizon,
    })
    if (result.ok === true) {
      setRefitResponse(result.data)
    } else if (result.ok === false) {
      setRefitError(result.error)
    }
    setRefitLoading(false)
  }
  const selectedRefit = refitResponse?.series_id === `S${store}_I${item}` ? refitResponse : null
  const liveRefit = selectedRefit?.forecast ?? null
  
  return <div className="flex min-w-0 flex-col gap-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex flex-wrap items-center gap-3"><h1>Forecast</h1><Badge variant="outline">Prophet model</Badge></div><p className="mt-2 text-muted-foreground">Predicted daily demand with an 80% confidence band</p></div><details className="max-w-sm rounded-lg border bg-card p-3 text-xs"><summary className="cursor-pointer font-medium">How to read this</summary><p className="mt-3 leading-5 text-muted-foreground">Indigo is the forecast; amber is actual sales. The shaded band shows uncertainty. Lower MAPE and RMSE mean better predictions. Backtest compares the model with the same held-out dates; Future shows January demand without known actuals.</p></details></div>
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground"><p>{mode === "future" ? "Metrics are measured on the Dec 2017 test window." : `Backtest · Dec 1–${horizon}, 2017 · same dates for model and baseline`}</p>{leastHelpful && <Link href={leastHelpful.href} className="text-primary underline-offset-4 hover:underline">{leastHelpful.label}</Link>}</div>
    
    {backendOnline && (
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Training end date
          <input
            aria-label="Training end date"
            type="date"
            min="2014-01-01"
            max="2017-12-31"
            value={trainEnd}
            onChange={event => setTrainEnd(event.target.value)}
            className="h-9 rounded-md border bg-background px-2 text-foreground"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Horizon
          <select
            aria-label="Re-fit horizon"
            value={refitHorizon}
            onChange={event => setRefitHorizon(Number(event.target.value) as 14 | 30)}
            className="h-9 rounded-md border bg-background px-2 text-foreground"
          >
            <option value={14}>14 days</option>
            <option value={30}>30 days</option>
          </select>
        </label>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefit}
          disabled={refitLoading || trainEnd < "2014-01-01" || trainEnd > "2017-12-31"}
          className="text-xs"
        >
          {refitLoading ? `Refitting (${refitElapsed}s)...` : "Re-fit live"}
        </Button>
        {refitLoading && <span className="text-xs text-muted-foreground">Running Prophet re-fit...</span>}
        {selectedRefit?.cached && (
          <Badge variant="secondary" className="text-xs">
            Cached
          </Badge>
        )}
        {refitError && <p role="alert" className="basis-full text-xs text-destructive">{refitError}</p>}
      </div>
    )}
    
    {error ? <Empty className="min-h-96 border bg-card"><EmptyHeader><EmptyTitle>Unable to load this forecast</EmptyTitle><EmptyDescription>Your selection is saved in the URL. Retry loading this series.</EmptyDescription></EmptyHeader><Button variant="outline" onClick={() => void mutate()}>Retry</Button></Empty> : !data ? <ForecastSkeleton /> : !data.history.length || !data[mode].model.length ? <Empty className="min-h-96 border"><EmptyHeader><EmptyTitle>No forecast available</EmptyTitle><EmptyDescription>Choose another store or item.</EmptyDescription></EmptyHeader></Empty> : <div className="flex min-w-0 flex-col gap-6 transition-opacity duration-150 data-[loading=true]:opacity-60" data-loading={isValidating} aria-busy={isValidating}>
      {/* Live re-fit metrics card */}
      {selectedRefit && (
        <div className="rounded-lg border bg-card p-4 text-xs">
          <div className="flex items-center justify-between mb-2">
            <span className="font-medium">Live re-fit metrics</span>
            {selectedRefit.cached && <Badge variant="secondary">Cached</Badge>}
            <span className="text-muted-foreground">Fit in {selectedRefit.fit_seconds.toFixed(2)}s</span>
          </div>
          {selectedRefit.metrics && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-muted-foreground">MAPE</div>
                <div className="font-medium">{selectedRefit.metrics.model.mape.toFixed(2)}%</div>
              </div>
              <div>
                <div className="text-muted-foreground">RMSE</div>
                <div className="font-medium">{selectedRefit.metrics.model.rmse.toFixed(2)}</div>
              </div>
            </div>
          )}
        </div>
      )}
      <ForecastMetrics series={data} horizon={horizon} />
      <ForecastChart series={data} horizon={horizon} mode={mode} liveRefit={liveRefit} />
      <RestockPreview store={store} horizon={horizon} />
    </div>}
    <p className="text-xs leading-5 text-muted-foreground">Prophet model trained on 2013–2017-11-30 · Dec 2017 held-out test · Future forecast through Jan 30, 2018.</p>
  </div>
}
