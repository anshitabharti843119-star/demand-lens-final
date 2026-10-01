"use client"

import { Info } from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip"
import { formatImprovement, formatPortfolioPercent, type PortfolioView } from "@/lib/portfolio-view"
import { cn } from "@/lib/utils"

export const mapeExplanation = "MAPE = average % error, lower is better. Each series has equal weight in the portfolio average."
export const improvementExplanation = "Relative error reduction: (baseline MAPE − model MAPE) / baseline MAPE × 100. Negative values mean the baseline is better."

export function PortfolioMetricLabel({ label, explanation }: { label: string; explanation: string }) {
  return <Tooltip><TooltipTrigger className="inline-flex min-h-8 items-center gap-1.5 text-left" aria-label={`${label}: ${explanation}`}><span>{label}</span><Info className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" /></TooltipTrigger><TooltipContent className="max-w-72">{explanation}</TooltipContent></Tooltip>
}

export function PortfolioMetrics({ view }: { view: PortfolioView }) {
  const metrics = [
    { label: "Win-rate", value: view.winRate === null ? "—" : formatPortfolioPercent(view.winRate), caption: `${view.wins.toLocaleString("en-US")} / ${view.count.toLocaleString("en-US")} series`, explanation: "Share of series where model MAPE is lower than baseline MAPE, using the same 30-day backtest horizon.", tone: "text-success" },
    { label: "Median MAPE improvement", value: view.median === null ? "—" : formatImprovement(view.median), caption: "Relative reduction in error", explanation: improvementExplanation, tone: view.median !== null && view.median < 0 ? "text-warning" : "text-success" },
    { label: "Average model MAPE", value: view.modelMape === null ? "—" : formatPortfolioPercent(view.modelMape), caption: "Average % error · lower is better", explanation: mapeExplanation, tone: "text-foreground" },
    { label: "Average baseline MAPE", value: view.baselineMape === null ? "—" : formatPortfolioPercent(view.baselineMape), caption: "28-day moving average baseline", explanation: mapeExplanation, tone: "text-foreground" },
  ]
  return <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Portfolio performance metrics">{metrics.map(metric => <Card key={metric.label} className="gap-3"><CardHeader><CardTitle><PortfolioMetricLabel label={metric.label} explanation={metric.explanation} /></CardTitle></CardHeader><CardContent className="flex flex-col gap-2"><p className={cn("text-3xl font-semibold tracking-tight tabular-nums", metric.tone)}>{metric.value}</p><p className="text-xs text-muted-foreground">{metric.caption}</p></CardContent></Card>)}</section>
}
