"use client"

import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, XAxis, YAxis } from "recharts"
import { ChartContainer, ChartTooltip } from "@/components/ui/chart"
import { EdaChartCard } from "@/components/eda/eda-chart-card"
import type { PortfolioBin } from "@/lib/portfolio-view"
import { improvementExplanation } from "./portfolio-metrics"

const config = { count: { label: "Series" }, model: { label: "Model wins", color: "var(--success)" }, baseline: { label: "Baseline wins", color: "var(--warning)" } }

export function PortfolioHistogram({ bins }: { bins: PortfolioBin[] }) {
  return <EdaChartCard title="Distribution of improvement" insight="Every series counts. Negative improvement is a model loss." info={`${improvementExplanation} Bins are 5 percentage points wide, including the lower bound and excluding the upper bound.`}>
    <p className="mb-3 text-xs text-muted-foreground">Number of series · 5% bins</p>
    <ChartContainer config={config} className="h-72 w-full aspect-auto" aria-label="Histogram of relative MAPE improvement. Negative bins are baseline wins; positive bins are model wins.">
      <BarChart accessibilityLayer data={bins} margin={{ top: 32, right: 12, left: 0, bottom: 8 }} barCategoryGap="8%">
        <CartesianGrid vertical={false} stroke="var(--border)" />
        <XAxis type="number" dataKey="midpoint" domain={[bins[0]?.start ?? -5, bins.at(-1)?.end ?? 5]} tickFormatter={value => `${value}%`} tickLine={false} axisLine={false} tickMargin={8} />
        <YAxis allowDecimals={false} width={32} tickLine={false} axisLine={false} />
        <ChartTooltip content={({ active, payload }) => {
          const bin = payload?.[0]?.payload as PortfolioBin | undefined
          if (!active || !bin) return null
          return <div className="rounded-lg border bg-card p-3 text-xs shadow-sm"><p className="font-medium">{bin.start}% to {bin.end}% (upper excluded)</p><p className="mt-1 text-muted-foreground">{bin.count.toLocaleString("en-US")} series</p></div>
        }} />
        <Bar dataKey="count" radius={[3, 3, 0, 0]} isAnimationActive={false}>{bins.map(bin => <Cell key={bin.start} fill={bin.start < 0 ? "var(--color-baseline)" : "var(--color-model)"} />)}</Bar>
        <ReferenceLine x={0} stroke="var(--muted-foreground)" strokeDasharray="4 4" label={{ content: () => <text x="50%" y={16} textAnchor="middle" fill="var(--foreground)" fontSize={10}>Baseline wins ← | → Model wins</text> }} />
      </BarChart>
    </ChartContainer>
    <p className="mt-3 text-center text-xs text-muted-foreground">Relative MAPE improvement (%) · zero = equal error</p>
  </EdaChartCard>
}
