"use client"

import type { EdaData } from "@/lib/types"
import { formatEdaUnits, monthLabels } from "@/lib/eda-view"
import { EdaChartCard } from "./eda-chart-card"

export function EdaHeatmap({ data }: { data: NonNullable<EdaData["month_year_heatmap"]> }) {
  if (!data.length) return null
  const min = Math.min(...data.map(row => row.avg_sales))
  const max = Math.max(...data.map(row => row.avg_sales))
  const years = [...new Set(data.map(row => row.year))].sort((a, b) => a - b)
  const values = new Map(data.map(row => [`${row.year}-${row.month}`, row.avg_sales]))
  const intensity = (value: number) => 8 + (max === min ? 0.5 : (value - min) / (max - min)) * 34
  return <EdaChartCard title="Seasonality at a glance" insight="Summer months stand out; each year starts from a higher base." info="Average units per item per day for each month and year. Darker indigo means higher demand; the color scale adapts to the selected store. Exact values are shown in each cell.">
    <div className="overflow-x-auto pb-2" role="region" aria-label="Monthly seasonality heatmap; scroll horizontally on small screens" tabIndex={0}>
      <div role="table" aria-label="Average daily item sales by month and year" className="flex min-w-[640px] flex-col gap-2">
        <div role="row" className="grid grid-cols-[48px_repeat(12,minmax(0,1fr))] gap-2 text-center text-xs text-muted-foreground"><span role="columnheader" className="sr-only">Year</span><span aria-hidden="true" />{monthLabels.map(month => <span role="columnheader" key={month}>{month}</span>)}</div>
        {years.map(year => <div role="row" key={year} className="grid grid-cols-[48px_repeat(12,minmax(0,1fr))] items-center gap-2">
          <span role="rowheader" className="text-xs text-muted-foreground">{year}</span>
          {monthLabels.map((month, i) => {
            const value = values.get(`${year}-${i + 1}`)
            return <div role="cell" key={month} className="flex h-10 items-center justify-center rounded-md text-xs" aria-label={`${month} ${year}: ${value === undefined ? "No data" : `${formatEdaUnits(value)} units per item per day`}`} style={{ background: value === undefined ? "var(--muted)" : `color-mix(in srgb, var(--primary) ${intensity(value)}%, var(--card))` }}>{value === undefined ? "—" : formatEdaUnits(value)}</div>
          })}
        </div>)}
      </div>
    </div>
    <div className="mt-4 flex items-center justify-end gap-2 text-xs text-muted-foreground"><span>Lower</span>{[8, 16, 25, 34, 42].map(opacity => <span key={opacity} className="size-3 rounded-sm" aria-hidden="true" style={{ background: `color-mix(in srgb, var(--primary) ${opacity}%, var(--card))` }} />)}<span>Higher daily sales</span></div>
  </EdaChartCard>
}
