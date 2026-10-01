"use client"

import { useEffect, useMemo, useState } from "react"
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, XAxis, YAxis } from "recharts"
import type { ForecastPoint, Horizon, Mode, SeriesData } from "@/lib/types"
import { forecastChartData, forecastDate, type ForecastChartPoint } from "@/lib/forecast-view"
import { formatUnits } from "@/lib/restock-view"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { ChartContainer, ChartTooltip } from "@/components/ui/chart"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { MetricHelp } from "./forecast-metrics"

const config = { history: { label: "History", color: "var(--history)" }, yhat: { label: "Forecast", color: "var(--forecast)" }, actual: { label: "Actual sales", color: "var(--actual)" }, baseline: { label: "Baseline", color: "var(--baseline)" } }
const liveRefitConfig = { liveRefit: { label: "Live re-fit", color: "var(--live-refit)" } }
function ForecastTooltip({ active, payload }: { active?: boolean; payload?: ReadonlyArray<{ payload?: ForecastChartPoint }> }) {
  const point = payload?.[0]?.payload
  if (!active || !point) return null
  return <div className="min-w-44 rounded-lg border bg-card p-3 text-xs shadow-sm"><p className="mb-2 font-medium">{forecastDate(point.ds)}</p><dl className="flex flex-col gap-2">{Object.entries({ ...config, ...liveRefitConfig }).map(([key, value]) => {
    const number = point[key as keyof ForecastChartPoint]
    return typeof number === "number" ? <div key={key} className="flex justify-between gap-6"><dt style={{ color: value.color }}>{value.label}</dt><dd>{formatUnits(number)}</dd></div> : null
  })}{point.lower !== undefined && <div className="flex justify-between gap-6"><dt>80% interval</dt><dd>{formatUnits(point.lower)}–{formatUnits(point.upper!)}</dd></div>}</dl></div>
}

export function ForecastChart({ series, horizon, mode, liveRefit }: { series: SeriesData; horizon: Horizon; mode: Mode; liveRefit?: ForecastPoint[] }) {
  const [range, setRange] = useState("90")
  const [visible, setVisible] = useState(["history", "yhat", "actual", "baseline", "band"])
  useEffect(() => {
    if (liveRefit?.length) {
      setVisible(current => current.includes("liveRefit") ? current : [...current, "liveRefit"])
    }
  }, [liveRefit])
  
  // Combine live refit series if provided
  const data = useMemo(() => {
    const baseData = forecastChartData(series, mode, horizon, Number(range))
    if (!liveRefit || liveRefit.length === 0) return baseData

    const points = new Map(baseData.map(point => [point.ds, point]))
    for (const point of liveRefit) {
      const existing = points.get(point.ds)
      points.set(point.ds, {
        ...(existing ?? { ds: point.ds }),
        liveRefit: point.yhat,
        liveRefitLower: point.yhat_lower,
        liveRefitUpper: point.yhat_upper,
      })
    }
    return [...points.values()].sort((left, right) => left.ds.localeCompare(right.ds))
  }, [series, mode, horizon, range, liveRefit])
  
  const start = mode === "backtest" ? "2017-12-01" : "2018-01-01"
  return <Card className="min-w-0"><CardHeader><div className="flex flex-wrap items-center justify-between gap-4"><div className="flex flex-col gap-1"><CardTitle>Daily demand forecast</CardTitle><CardDescription>Store {series.store} · Item {series.item} · units per day</CardDescription></div><ToggleGroup aria-label="History range" value={[range]} onValueChange={values => { if (values[0]) setRange(values[0]) }} variant="outline" spacing={0}><ToggleGroupItem value="90">90d</ToggleGroupItem><ToggleGroupItem value="180">180d</ToggleGroupItem><ToggleGroupItem value="365">1y</ToggleGroupItem></ToggleGroup></div></CardHeader>
    <CardContent className="min-w-0"><ChartContainer config={{ ...config, ...liveRefitConfig }} className="h-[340px] w-full sm:h-[420px]" role="img" aria-label={`${horizon}-day ${mode} demand forecast for Store ${series.store}, Item ${series.item}, with an 80% confidence band${mode === "backtest" ? ", actual sales and moving-average baseline" : ""}`}>
      <ComposedChart accessibilityLayer data={data} margin={{ top: 24, right: 12, bottom: 0, left: -16 }}><CartesianGrid vertical={false} /><XAxis dataKey="ds" tickFormatter={forecastDate} minTickGap={45} tickLine={false} axisLine={false} /><YAxis tickLine={false} axisLine={false} width={48} /><ChartTooltip content={<ForecastTooltip />} />
        <Area dataKey="lower" stackId="interval" stroke="none" fill="transparent" hide={!visible.includes("band")} isAnimationActive={false} />
        <Area dataKey="band" stackId="interval" stroke="none" fill="var(--band)" hide={!visible.includes("band")} isAnimationActive={false} />
        <ReferenceLine x={start} stroke="var(--muted-foreground)" strokeDasharray="4 4" label={{ value: "Forecast starts", position: "insideTopRight", fill: "var(--muted-foreground)", fontSize: 10 }} />
        {Object.entries(config).map(([key]) => <Line key={key} dataKey={key} name={config[key as keyof typeof config].label} stroke={`var(--color-${key})`} strokeWidth={2} strokeDasharray={key === "baseline" ? "5 5" : undefined} dot={false} activeDot={{ r: 4 }} hide={!visible.includes(key) || (mode === "future" && ["actual", "baseline"].includes(key))} isAnimationActive={false} />)}
        {liveRefit && liveRefit.length > 0 && <Line key="liveRefit" dataKey="liveRefit" name="Live re-fit" stroke="var(--color-live-refit)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} hide={!visible.includes("liveRefit")} isAnimationActive={false} />}
      </ComposedChart>
    </ChartContainer><div className="mt-4 flex flex-wrap items-center justify-center gap-2"><ToggleGroup multiple aria-label="Visible chart series" value={visible} onValueChange={setVisible} className="flex-wrap">{Object.entries(config).filter(([key]) => mode === "backtest" || !["actual", "baseline"].includes(key)).map(([key, value]) => <ToggleGroupItem key={key} value={key} className="gap-2 text-xs"><span className="h-0.5 w-4" style={{ background: value.color }} />{value.label}</ToggleGroupItem>)}<ToggleGroupItem value="band" className="gap-2 text-xs"><span className="h-3 w-4 rounded-sm bg-band" />80% band</ToggleGroupItem>{liveRefit && liveRefit.length > 0 && <ToggleGroupItem value="liveRefit" className="gap-2 text-xs"><span className="h-0.5 w-4" style={{ background: "var(--live-refit)" }} />Live re-fit</ToggleGroupItem>}</ToggleGroup><MetricHelp label="confidence band" text="The shaded range targets 80% of possible daily sales outcomes; it is not a guarantee." /></div></CardContent>
  </Card>
}
