"use client"

import { Bar, BarChart, CartesianGrid, Cell, LabelList, XAxis, YAxis } from "recharts"
import { type EdaView, formatCompactUnits } from "@/lib/eda-view"
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { EdaChartCard, EdaChartEmpty } from "./eda-chart-card"

const weeklyConfig = { avg_sales: { label: "Average daily sales", color: "var(--history)" } }
const weekendConfig = {
  weekday_avg: { label: "Weekday", color: "var(--history)" },
  weekend_avg: { label: "Weekend", color: "var(--primary)" },
}

export function EdaWeeklyChart({ data, uplift }: { data: EdaView["weekly"]; uplift: number | null }) {
  return <EdaChartCard title="Weekly seasonality" insight={uplift === null ? "Compare average sales across the week." : `Saturday and Sunday sell about ${uplift.toFixed(1)}% more.`} info="Average units per item per day for each weekday (Monday first), over 2013–2017. All stores averages the five stores equally; weekend bars are highlighted.">
    {!data.length ? <EdaChartEmpty /> : <>
      <p className="mb-4 flex min-h-8 items-center text-xs text-muted-foreground">Units / item / day</p>
      <ChartContainer config={weeklyConfig} className="h-56 w-full aspect-auto" aria-label="Average daily item sales from Monday to Sunday; Saturday and Sunday highlighted">
        <BarChart accessibilityLayer data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="day" tickLine={false} axisLine={false} tickMargin={8} interval={0} />
          <YAxis width={36} tickFormatter={formatCompactUnits} tickLine={false} axisLine={false} />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Bar dataKey="avg_sales" radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false}>{data.map(row => <Cell key={row.day} fill={row.fill} />)}</Bar>
        </BarChart>
      </ChartContainer>
      <div className="flex h-8 items-end justify-center gap-4 text-xs text-muted-foreground"><span className="flex items-center gap-2"><span className="size-2 rounded-sm bg-history" />Weekday</span><span className="flex items-center gap-2"><span className="size-2 rounded-sm bg-primary" />Weekend</span></div>
    </>}
  </EdaChartCard>
}

export function EdaWeekendChart({ data }: { data: EdaView["weekend"] }) {
  return <EdaChartCard title="Weekend effect" insight="The weekend uplift is consistent across stores." info="Average units per item per day, comparing Monday–Friday with Saturday–Sunday. Labels show the percentage increase over each store’s weekday average.">
    {!data.length ? <EdaChartEmpty /> : <>
      <p className="mb-4 flex min-h-8 items-center text-xs text-muted-foreground">Units / item / day · uplift above bars</p>
      <ChartContainer config={weekendConfig} className="h-64 w-full aspect-auto" aria-label="Weekday versus weekend average sales per store with percentage uplift labels">
        <BarChart accessibilityLayer data={data} margin={{ top: 24, right: 8, left: 0, bottom: 0 }} barGap={3}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} interval={0} tick={{ fontSize: 10 }} />
          <YAxis width={36} tickFormatter={formatCompactUnits} tickLine={false} axisLine={false} domain={[0, (max: number) => Math.ceil(max * 1.25)]} />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Bar dataKey="weekday_avg" fill="var(--color-weekday_avg)" radius={[3, 3, 0, 0]} maxBarSize={28} isAnimationActive={false} />
          <Bar dataKey="weekend_avg" fill="var(--color-weekend_avg)" radius={[3, 3, 0, 0]} maxBarSize={28} isAnimationActive={false}>
            <LabelList dataKey="uplift_label" position="top" offset={10} fill="var(--foreground)" fontSize={10} />
          </Bar>
          <ChartLegend content={<ChartLegendContent />} />
        </BarChart>
      </ChartContainer>
    </>}
  </EdaChartCard>
}
