"use client"

import { CartesianGrid, ReferenceLine, Scatter, ScatterChart, XAxis, YAxis, ZAxis } from "recharts"
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip } from "@/components/ui/chart"
import { EdaChartCard } from "@/components/eda/eda-chart-card"
import { formatImprovement, formatPortfolioPercent } from "@/lib/portfolio-view"
import type { PortfolioRow } from "@/lib/types"
import { mapeExplanation } from "./portfolio-metrics"

const config = { model: { label: "Model wins", color: "var(--success)" }, baseline: { label: "Baseline wins", color: "var(--warning)" } }

export function PortfolioScatter({ rows, max }: { rows: PortfolioRow[]; max: number }) {
  return <EdaChartCard title="Model vs baseline error" insight="Below the diagonal, the model has lower error." info={`${mapeExplanation} The dashed diagonal marks equal error; points above it are baseline wins.`}>
    <p className="mb-3 text-xs text-muted-foreground">Model MAPE (%)</p>
    <ChartContainer config={config} className="h-72 w-full aspect-auto" aria-label="Scatter plot of baseline MAPE on the horizontal axis and model MAPE on the vertical axis. Points below the equal-error line favor the model.">
      <ScatterChart accessibilityLayer margin={{ top: 16, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--border)" />
        <XAxis type="number" dataKey="baseline_mape" name="Baseline MAPE" unit="%" domain={[0, max]} tickLine={false} axisLine={false} tickMargin={8} />
        <YAxis type="number" dataKey="model_mape" name="Model MAPE" unit="%" domain={[0, max]} width={40} tickLine={false} axisLine={false} />
        <ZAxis range={[32, 32]} />
        <ReferenceLine segment={[{ x: 0, y: 0 }, { x: max, y: max }]} stroke="var(--muted-foreground)" strokeDasharray="4 4" label={{ value: "Equal error", position: "insideTopLeft", fill: "var(--muted-foreground)", fontSize: 10 }} />
        <ChartTooltip cursor={{ strokeDasharray: "3 3" }} content={({ active, payload }) => {
          const row = payload?.[0]?.payload as PortfolioRow | undefined
          if (!active || !row) return null
          return <div className="flex flex-col gap-1 rounded-lg border bg-card p-3 text-xs shadow-sm"><p className="font-semibold">{row.series_id} · Store {row.store}, Item {row.item}</p><p>Model MAPE: {formatPortfolioPercent(row.model_mape)}</p><p>Baseline MAPE: {formatPortfolioPercent(row.baseline_mape)}</p><p>Improvement: {formatImprovement(row.improvement_pct)}</p><p className="text-muted-foreground">{row.winner === "model" ? "Model wins" : "Baseline wins"}</p></div>
        }} />
        <Scatter name="model" data={rows.filter(row => row.winner === "model")} fill="var(--color-model)" fillOpacity={0.8} isAnimationActive={false} />
        <Scatter name="baseline" data={rows.filter(row => row.winner === "baseline")} fill="var(--color-baseline)" shape="diamond" isAnimationActive={false} />
        <ChartLegend content={<ChartLegendContent />} />
      </ScatterChart>
    </ChartContainer>
    <p className="mt-3 text-center text-xs text-muted-foreground">Baseline MAPE (%) · dashed line = equal error</p>
  </EdaChartCard>
}
