"use client"

import { useState } from "react"
import { ChevronDown, RotateCcw, SlidersHorizontal } from "lucide-react"
import type { RestockOptions } from "@/lib/restock"
import type { RestockFilters } from "@/lib/restock-view"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel, FieldDescription } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import { Separator } from "@/components/ui/separator"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectGroup, SelectItem } from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

const levels = [{ value: "0.9", label: "90%" }, { value: "0.95", label: "95%" }, { value: "0.99", label: "99%" }]
interface Props { options: RestockOptions; filters: RestockFilters; onOptions: (patch: Partial<RestockOptions>) => void; onFilters: (patch: Partial<RestockFilters>) => void; onReset: () => void }

export function RestockControls({ options, filters, onOptions, onFilters, onReset }: Props) {
  const [expanded, setExpanded] = useState(false)
  return <Card className="gap-0 self-start overflow-hidden lg:sticky lg:top-6">
    <CardHeader className="gap-2 pb-5">
      <div className="flex items-center justify-between gap-2"><CardTitle><span className="flex items-center gap-2"><SlidersHorizontal className="size-4 text-muted-foreground" />Assumptions & filters</span></CardTitle><Button variant="ghost" size="icon" className="lg:hidden" aria-label="Toggle assumptions and filters" aria-expanded={expanded} aria-controls="restock-controls" onClick={() => setExpanded(!expanded)}><ChevronDown /></Button></div>
      <CardDescription>Plan your next replenishment.</CardDescription>
    </CardHeader>
    <div id="restock-controls" className={cn(expanded ? "block" : "hidden", "lg:block")}>
      <CardContent className="selector-controls">
        <FieldGroup className="gap-6">
          <Field><FieldLabel id="restock-horizon">Forecast horizon</FieldLabel><ToggleGroup spacing={0} aria-labelledby="restock-horizon" value={[String(options.horizon)]} onValueChange={values => { if (values[0]) onOptions({ horizon: values[0] === "14" ? 14 : 30 }) }}><ToggleGroupItem className="flex-1" value="14">14 days</ToggleGroupItem><ToggleGroupItem className="flex-1" value="30">30 days</ToggleGroupItem></ToggleGroup></Field>
          <Field><FieldLabel htmlFor="service-level">Service level</FieldLabel><Select items={levels} value={String(options.serviceLevel)} onValueChange={value => { if (value) onOptions({ serviceLevel: Number(value) as RestockOptions["serviceLevel"] }) }}><SelectTrigger id="service-level" className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup>{levels.map(level => <SelectItem key={level.value} value={level.value}>{level.label}</SelectItem>)}</SelectGroup></SelectContent></Select><FieldDescription>Higher levels add more safety stock.</FieldDescription></Field>
          <Field><div className="flex items-center justify-between"><FieldLabel id="lead-time-label">Lead time</FieldLabel><output className="text-xs font-medium" data-testid="lead-time-value">{options.leadTime} days</output></div><Slider aria-labelledby="lead-time-label" className="py-3" min={1} max={14} step={1} value={[options.leadTime]} onValueChange={value => onOptions({ leadTime: Array.isArray(value) ? value[0] : value })} /><div className="flex justify-between text-xs text-muted-foreground"><span>1 day</span><span>14 days</span></div></Field>
          <Field><div className="flex items-center justify-between"><FieldLabel id="stock-multiplier-label">Stock multiplier</FieldLabel><output className="text-xs font-medium" data-testid="stock-multiplier-value">{options.stockMultiplier.toFixed(1)}x</output></div><Slider aria-labelledby="stock-multiplier-label" className="py-3" min={0.5} max={2} step={0.1} value={[options.stockMultiplier]} onValueChange={value => onOptions({ stockMultiplier: Array.isArray(value) ? value[0] : value })} /><FieldDescription>Scales the assumed current stock</FieldDescription></Field>
          <Separator />
          <Field><FieldLabel id="restock-store">Store</FieldLabel><ToggleGroup spacing={0} aria-labelledby="restock-store" value={[filters.store]} onValueChange={values => { if (values[0]) onFilters({ store: values[0] }) }}>{["all", "1", "2", "3", "4", "5"].map(store => <ToggleGroupItem className="min-w-0 flex-1 px-2!" key={store} value={store} aria-label={store === "all" ? "All stores" : `Store ${store}`}>{store === "all" ? "All" : store}</ToggleGroupItem>)}</ToggleGroup></Field>
          <Field><FieldLabel id="restock-priority">Priority</FieldLabel><ToggleGroup spacing={0} aria-labelledby="restock-priority" value={[filters.priority]} onValueChange={values => { if (values[0]) onFilters({ priority: values[0] }) }}>{["all", "HIGH", "MEDIUM", "LOW"].map(priority => <ToggleGroupItem className="min-w-0 flex-1 px-2! text-[11px]!" key={priority} value={priority}>{priority === "all" ? "All" : priority}</ToggleGroupItem>)}</ToggleGroup></Field>
          <Field><FieldLabel htmlFor="restock-search">Search item number</FieldLabel><Input id="restock-search" inputMode="numeric" placeholder="e.g. 23" value={filters.search} onChange={event => onFilters({ search: event.target.value })} /></Field>
        </FieldGroup>
      </CardContent>
      <CardFooter className="mt-6"><Button variant="ghost" className="w-full" onClick={onReset}><RotateCcw data-icon="inline-start" />Reset to defaults</Button></CardFooter>
    </div>
  </Card>
}
