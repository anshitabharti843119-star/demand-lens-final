"use client"

import { useMemo } from "react"
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"
import type { RestockInput, RestockRow } from "@/lib/types"
import type { RestockOptions } from "@/lib/restock"
import { formatUnits, formatCover } from "@/lib/restock-view"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { Separator } from "@/components/ui/separator"
import { RestockPriority } from "./restock-status"

interface Props { row: RestockRow | undefined; input: RestockInput | undefined; options: RestockOptions; onClose: () => void }
export function RestockSheet({ row, input, options, onClose }: Props) {
  const data = useMemo(() => input?.yhat_future.slice(0, options.horizon).map((demand, i) => ({ date: `Jan ${i + 1}`, demand })) ?? [], [input, options.horizon])
  return <Sheet open={!!row} onOpenChange={open => { if (!open) onClose() }}>
    <SheetContent side="right" className="overflow-y-auto data-[side=right]:w-full data-[side=right]:sm:max-w-lg">
      {row && <>
        <SheetHeader className="gap-2 border-b p-6"><SheetTitle>Item {row.item} · Store {row.store}</SheetTitle><SheetDescription>Restock calculation · {options.horizon}-day horizon</SheetDescription><div className="pt-2"><RestockPriority priority={row.priority} /></div></SheetHeader>
        <div className="flex flex-col gap-6 px-6 pb-8">
          <section aria-label="Recommended order" className="rounded-xl border border-primary/20 bg-primary/5 p-5"><p className="text-xs text-muted-foreground">Recommended order</p><p className="mt-2 text-4xl font-semibold tracking-tight text-primary">{formatUnits(row.restock_qty)} <span className="text-sm font-normal">units</span></p><p className="mt-2 text-xs text-muted-foreground">{formatCover(row.days_of_cover)} days of cover · {options.leadTime}-day lead time</p></section>
          <Card><CardHeader><CardTitle>Daily demand forecast</CardTitle><CardDescription>Jan 1–{options.horizon}, 2018 · units per day</CardDescription></CardHeader><CardContent><ChartContainer config={{ demand: { label: "Forecast", color: "var(--forecast)" } }} className="h-52 w-full" role="img" aria-label={`Daily forecast for Item ${row.item}, Store ${row.store}, totaling ${formatUnits(row.forecast_demand)} units over ${options.horizon} days`}><LineChart accessibilityLayer data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}><CartesianGrid vertical={false} /><XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={28} /><YAxis tickLine={false} axisLine={false} /><ChartTooltip content={<ChartTooltipContent />} /><Line dataKey="demand" type="monotone" stroke="var(--color-demand)" strokeWidth={2} dot={false} isAnimationActive={false} /></LineChart></ChartContainer></CardContent></Card>
          <section aria-labelledby="calculation-title" className="flex flex-col gap-4"><h2 id="calculation-title">Calculation breakdown</h2><dl className="flex flex-col gap-4 text-sm">
            {[[`Forecast demand · ${options.horizon} days (D)`, row.forecast_demand], ["Safety stock (SS)", row.safety_stock], ["Current stock", row.current_stock]].map(([label, value]) => <div key={label} className="flex items-center justify-between gap-4"><dt className="text-muted-foreground">{label}</dt><dd className="font-medium">{formatUnits(Number(value))}</dd></div>)}
            <Separator /><div className="flex items-center justify-between gap-4"><dt>Restock quantity</dt><dd className="font-semibold text-primary">{formatUnits(row.restock_qty)} units</dd></div>
          </dl><p className="rounded-lg bg-muted p-4 text-sm leading-6" data-testid="restock-breakdown">D = {formatUnits(row.forecast_demand)}, SS = {formatUnits(row.safety_stock)}, current stock = {formatUnits(row.current_stock)} → order {formatUnits(row.restock_qty)}</p><p className="text-xs leading-5 text-muted-foreground">Order = max(0, ceil(D + SS − current stock)). Orders round up to whole units; displayed inputs round to 2 decimals. Calculations use full precision.</p></section>
          <section className="flex flex-col gap-2 text-xs text-muted-foreground" aria-label="Calculation assumptions"><p>Service level: {(options.serviceLevel * 100).toFixed(0)}% · Lead time: {options.leadTime} days · Stock multiplier: {options.stockMultiplier.toFixed(1)}x</p><p>Safety stock = z × daily demand standard deviation × √lead time. Days of cover = current stock ÷ average forecast demand.</p><p>HIGH: cover below lead time. MEDIUM: cover below the forecast horizon. LOW: cover meets the horizon.</p><p>Uploaded stock is used when selected; series missing from the upload use simulated stock.</p></section>
        </div>
      </>}
    </SheetContent>
  </Sheet>
}
