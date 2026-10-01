"use client"

import { useState } from "react"
import { Area, CartesianGrid, ComposedChart, Line, XAxis, YAxis } from "recharts"
import type { EdaData } from "@/lib/types"
import { formatCompactUnits, monthLabels } from "@/lib/eda-view"
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { Button } from "@/components/ui/button"
import { EdaChartCard, EdaChartEmpty } from "./eda-chart-card"

const config = {
  sales: { label: "Monthly sales", color: "var(--primary)" },
  rolling_12m: { label: "12-month average", color: "var(--baseline)" },
}

export function EdaTrendChart({ data }: { data: EdaData["monthly_total"] }) {
  const [showRolling, setShowRolling] = useState(true)
  const hasRolling = data.some(row => row.rolling_12m !== undefined)
  return <EdaChartCard title="Trend" insight="Sales grow steadily with a summer peak every year." info="Total units sold across all 50 items per selected store, each month. The trailing average uses 12 complete months and starts in December 2013.">
    {!data.length ? <EdaChartEmpty /> : <>
      <div className="mb-4 flex min-h-8 items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">Units / month</span>
        {hasRolling && <Button variant="outline" size="sm" aria-pressed={showRolling} onClick={() => setShowRolling(value => !value)}>12-month average {showRolling ? "on" : "off"}</Button>}
      </div>
      <ChartContainer config={config} className="h-64 w-full aspect-auto" aria-label="Monthly total sales from January 2013 to December 2017, with optional trailing 12-month average">
        <ComposedChart accessibilityLayer data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="month" ticks={["2013-01", "2014-01", "2015-01", "2016-01", "2017-01"]} tickFormatter={value => String(value).slice(0, 4)} tickLine={false} axisLine={false} tickMargin={8} minTickGap={12} />
          <YAxis tickFormatter={formatCompactUnits} width={44} tickLine={false} axisLine={false} />
          <ChartTooltip content={<ChartTooltipContent labelFormatter={value => `${monthLabels[Number(String(value).slice(5)) - 1]} ${String(value).slice(0, 4)}`} />} />
          <Area dataKey="sales" type="monotone" fill="var(--band)" stroke="var(--color-sales)" strokeWidth={2} dot={false} isAnimationActive={false} />
          {showRolling && hasRolling && <Line dataKey="rolling_12m" type="monotone" stroke="var(--color-rolling_12m)" strokeWidth={2} strokeDasharray="4 4" dot={false} connectNulls={false} isAnimationActive={false} />}
          <ChartLegend content={<ChartLegendContent />} />
        </ComposedChart>
      </ChartContainer>
    </>}
  </EdaChartCard>
}
