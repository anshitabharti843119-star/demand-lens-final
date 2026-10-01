"use client"

import { Check, TriangleAlert, Info } from "lucide-react"
import type { Horizon, SeriesData } from "@/lib/types"
import { forecastVerdict } from "@/lib/forecast-view"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip"

export function WinnerBadge({ winner }: { winner: "model" | "baseline" }) {
  return <Badge variant="outline" className={cn("whitespace-normal", winner === "model" ? "border-success/25 text-success" : "border-warning/25 text-warning")}>
    {winner === "model" ? <Check data-icon="inline-start" /> : <TriangleAlert data-icon="inline-start" />}
    {winner === "model" ? "Model beats baseline" : "Baseline wins on this series"}
  </Badge>
}

export function MetricHelp({ label, text }: { label: string; text: string }) {
  return <Tooltip><TooltipTrigger aria-label={`About ${label}`} className="inline-flex shrink-0 rounded-sm text-muted-foreground"><Info className="size-3.5" aria-hidden="true" /></TooltipTrigger><TooltipContent className="max-w-64">{text}</TooltipContent></Tooltip>
}

export function ForecastMetrics({ series, horizon }: { series: SeriesData; horizon: Horizon }) {
  const { metrics, improvement, winner, coverage } = forecastVerdict(series, horizon)
  const cards = [
    { label: "Model MAPE", value: `${metrics.model.mape.toFixed(1)}%`, caption: "Average error · lower is better", help: "MAPE is the average percentage error between predictions and actual sales; lower is better." },
    { label: "Baseline MAPE", value: `${metrics.baseline.mape.toFixed(1)}%`, caption: "28-day moving average", help: "A simple forecast using the average of the last 28 training days, evaluated on the same dates." },
    { label: "Model RMSE", value: metrics.model.rmse.toFixed(1), caption: `units/day · baseline ${metrics.baseline.rmse.toFixed(1)}`, help: "RMSE measures typical forecast error in daily units and penalizes larger misses; lower is better." },
    { label: "Interval coverage", value: `${coverage.toFixed(1)}%`, caption: `Actuals inside band · ${horizon} days`, help: "The share of actual sales inside the forecast band on the selected test horizon; the target is 80%." },
  ]
  return <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6" aria-label="Forecast metrics">
    <Card className="forecast-verdict sm:col-span-2"><CardHeader><CardDescription>Model vs. baseline</CardDescription><WinnerBadge winner={winner} /></CardHeader><CardContent><p className={cn("text-3xl font-semibold tracking-tight", winner === "model" ? "text-success" : "text-warning")}>{Math.abs(improvement).toFixed(1)}% <span className="text-lg font-medium">{winner === "model" ? "lower" : "higher"} error</span></p><p className="mt-2 text-xs leading-5 text-muted-foreground">{winner === "model" ? "A more accurate signal for your next stock decision." : "The simple baseline is more accurate here. We show the losses, too."}</p></CardContent></Card>
    {cards.map(card => <Card key={card.label} className="min-w-0"><CardHeader><CardTitle><span className="flex items-center justify-between gap-2 text-xs font-medium text-muted-foreground">{card.label}<MetricHelp label={card.label} text={card.help} /></span></CardTitle></CardHeader><CardContent><p className="text-3xl font-semibold tracking-tight">{card.value}</p><p className="mt-3 text-xs leading-5 text-muted-foreground">{card.caption}</p>{card.label === "Model RMSE" && <span className={cn("mt-1 block text-xs", metrics.model.rmse < metrics.baseline.rmse ? "text-success" : "text-warning")}>{metrics.model.rmse < metrics.baseline.rmse ? "Better" : "Worse"} than baseline</span>}</CardContent></Card>)}
  </div>
}
