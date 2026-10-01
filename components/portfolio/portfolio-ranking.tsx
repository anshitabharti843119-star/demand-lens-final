"use client"

import Link from "next/link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription } from "@/components/ui/empty"
import { formatImprovement, formatPortfolioPercent, portfolioForecastHref } from "@/lib/portfolio-view"
import type { PortfolioRow } from "@/lib/types"
import { cn } from "@/lib/utils"
import { improvementExplanation, mapeExplanation, PortfolioMetricLabel } from "./portfolio-metrics"

export function PortfolioRanking({ rows, worst = false }: { rows: PortfolioRow[]; worst?: boolean }) {
  const title = worst ? "Worst 10 (baseline wins)" : "Top 10 improvements"
  return <Card className="min-w-0 gap-4">
    <CardHeader><CardTitle>{title}</CardTitle><CardDescription>{worst ? "Largest losses first. No losses are hidden." : "Largest relative reductions in MAPE first."} Open a series to inspect its backtest.</CardDescription></CardHeader>
    <CardContent>
      {!rows.length ? <Empty><EmptyHeader><EmptyTitle>{worst ? "No baseline wins in this selection" : "No series to rank"}</EmptyTitle><EmptyDescription>Choose another store to compare more series.</EmptyDescription></EmptyHeader></Empty> : <Table aria-label={title} className="text-xs tabular-nums">
        <TableHeader><TableRow><TableHead scope="col">Series</TableHead><TableHead scope="col" className="text-right"><PortfolioMetricLabel label="Model" explanation={mapeExplanation} /></TableHead><TableHead scope="col" className="text-right"><PortfolioMetricLabel label="Baseline" explanation={mapeExplanation} /></TableHead><TableHead scope="col" className="text-right"><PortfolioMetricLabel label="Improvement" explanation={improvementExplanation} /></TableHead></TableRow></TableHeader>
        <TableBody>{rows.map(row => {
          const href = portfolioForecastHref(row)
          return <TableRow key={row.series_id} className="group relative focus-within:bg-muted/50">
            <TableCell><Link href={href} prefetch={false} aria-label={`Inspect Store ${row.store}, Item ${row.item}, 30-day backtest`} className="inline-flex min-h-11 flex-col justify-center font-medium underline-offset-4 after:absolute after:inset-0 hover:underline focus-visible:outline-2 focus-visible:outline-primary"><span>Item {row.item}</span><span className="text-[10px] font-normal text-muted-foreground">Store {row.store} · {row.series_id}</span></Link></TableCell>
            <TableCell className="text-right">{formatPortfolioPercent(row.model_mape)}</TableCell><TableCell className="text-right">{formatPortfolioPercent(row.baseline_mape)}</TableCell><TableCell className={cn("text-right font-semibold", row.improvement_pct < 0 ? "text-warning" : row.improvement_pct > 0 ? "text-success" : "text-muted-foreground")}>{formatImprovement(row.improvement_pct)}</TableCell>
          </TableRow>
        })}</TableBody>
      </Table>}
    </CardContent>
  </Card>
}
