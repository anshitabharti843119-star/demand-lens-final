"use client"

import useSWR from "swr"
import { useSearchParams } from "next/navigation"
import { Info, RefreshCw } from "lucide-react"
import { getManifest, getRestockInputs, getSeries } from "@/lib/data"
import { readSelection } from "@/lib/selection"
import { computeRestock } from "@/lib/restock"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyContent } from "@/components/ui/empty"
import { PageSkeleton } from "@/components/page-skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

async function loadData([, id, horizon]: readonly [string, string, 14 | 30]) {
  const [manifest, series, inputs] = await Promise.all([getManifest(), getSeries(id), getRestockInputs()])
  return { manifest, series, rows: computeRestock(inputs, { horizon, serviceLevel: 0.95, leadTime: 3, stockMultiplier: 1 }).filter(row => row.restock_qty > 0).slice(0, 5) }
}

export function DataCheck() {
  const params = useSearchParams()
  const { store, item, horizon } = readSelection(params)
  const id = `S${store}_I${item}`
  const { data, error, isLoading, mutate } = useSWR(["data-check", id, horizon] as const, loadData)
  if (isLoading) return <PageSkeleton />
  if (error) return <Empty className="min-h-80 border bg-card"><EmptyHeader><EmptyTitle>Could not load series data</EmptyTitle><EmptyDescription>{error instanceof Error ? error.message : "An unexpected error occurred."}</EmptyDescription></EmptyHeader><EmptyContent><Button onClick={() => mutate()}><RefreshCw />Retry</Button></EmptyContent></Empty>
  if (!data) return <Empty><EmptyHeader><EmptyTitle>No data available</EmptyTitle></EmptyHeader><EmptyContent><Button onClick={() => mutate()}>Retry</Button></EmptyContent></Empty>
  return <div className="flex flex-col gap-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div className="flex flex-col gap-2"><h1>Data check</h1><p className="text-muted-foreground">Developer diagnostics · {id} · {horizon}-day horizon</p></div><Badge variant="outline">Developer diagnostics</Badge></div>
    <Card><CardHeader><CardTitle>Data contract</CardTitle><CardDescription>{data.manifest.series_ids.length.toLocaleString("en-US")} series · {data.series.history.length} history points · {data.series.backtest.actual.length} backtest days · {data.series.future.model.length} future days</CardDescription></CardHeader><CardContent><pre className="max-w-full overflow-auto text-xs leading-6">{JSON.stringify(data.manifest, (key, value) => key === "series_ids" || key === "items" ? `${value.length} entries` : value, 2)}</pre></CardContent></Card>
    <Card><CardHeader><CardTitle className="flex items-center gap-2">Series metrics<Tooltip><TooltipTrigger render={<Button size="icon-xs" variant="ghost" aria-label="Metric definitions" />}><Info /></TooltipTrigger><TooltipContent>MAPE = average % error, lower is better. RMSE = root mean square error in units/day, lower is better.</TooltipContent></Tooltip></CardTitle><CardDescription>Metrics computed from exported JSON backtest arrays (2dp). h14=first 14 days, h30=first 30 days, MAPE excludes actual==0.</CardDescription></CardHeader><CardContent><pre className="overflow-auto text-xs leading-6">{JSON.stringify(data.series.metrics, null, 2)}</pre></CardContent></Card>
    <Card><CardHeader><CardTitle>First 5 restock rows</CardTitle><CardDescription>Stock levels are simulated (dataset has no inventory data). Defaults: 95% service level, 3-day lead time, 1× stock. Sorted by days of cover.</CardDescription></CardHeader><CardContent><pre className="overflow-auto text-xs leading-6">{JSON.stringify(data.rows, null, 2)}</pre></CardContent></Card>
  </div>
}
