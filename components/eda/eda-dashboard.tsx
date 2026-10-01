"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { getEda } from "@/lib/data"
import { selectEda, type EdaStoreFilter } from "@/lib/eda-view"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Field, FieldLabel } from "@/components/ui/field"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { EdaTrendChart } from "./eda-trend-chart"
import { EdaWeeklyChart, EdaWeekendChart } from "./eda-seasonality-charts"
import { EdaHeatmap } from "./eda-heatmap"
import { EdaQuality } from "./eda-quality"

const storeOptions = [{ value: "all", label: "All stores" }, ...[1, 2, 3, 4, 5].map(store => ({ value: String(store), label: `Store ${store}` }))]

export function EdaDashboard() {
  const { data, error, mutate } = useSWR("eda", getEda, { revalidateOnFocus: false })
  const [store, setStore] = useState<EdaStoreFilter>("all")
  const view = useMemo(() => data ? selectEda(data, store) : null, [data, store])
  const empty = view && !view.monthly.length && !view.weekly.length && !view.weekend.length && !view.heatmap.length
  return <div className="flex flex-col gap-6">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex flex-col gap-2"><h1>Exploratory data analysis</h1><p className="text-muted-foreground">Understand the patterns behind your sales.</p><div className="flex flex-wrap items-center gap-2"><Badge variant="outline">Kaggle Store-Item · 2013–2017</Badge><span className="text-xs text-muted-foreground">2013–2017 · {store === "all" ? "All 5 stores" : `Store ${store}`} · 50 items per store</span></div></div>
      <Field className="w-44"><FieldLabel htmlFor="eda-store">Store</FieldLabel><Select items={storeOptions} value={String(store)} onValueChange={value => { if (value !== null) setStore(value === "all" ? "all" : Number(value)) }}><SelectTrigger id="eda-store" className="min-h-11 w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup>{storeOptions.map(option => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectGroup></SelectContent></Select></Field>
    </header>
    {error ? <Card><CardContent><Empty role="alert"><EmptyHeader><EmptyTitle>Unable to load sales patterns</EmptyTitle><EmptyDescription>Please retry loading the exploratory data.</EmptyDescription></EmptyHeader><Button variant="outline" onClick={() => { void mutate() }}>Retry</Button></Empty></CardContent></Card>
      : !view ? <div className="grid gap-6 xl:grid-cols-3" role="status" aria-label="Loading exploratory data">{[0, 1, 2].map(index => <Card key={index}><CardHeader className="gap-3"><Skeleton className="h-5 w-32" /><Skeleton className="h-10 w-full" /></CardHeader><CardContent><Skeleton className="h-72 w-full" /></CardContent></Card>)}</div>
      : empty ? <Card><CardContent><Empty><EmptyHeader><EmptyTitle>No sales data for this store</EmptyTitle><EmptyDescription>Choose another store or retry loading the data.</EmptyDescription></EmptyHeader><div className="flex gap-2"><Button variant="outline" onClick={() => setStore("all")}>All stores</Button><Button variant="outline" onClick={() => { void mutate() }}>Retry</Button></div></Empty></CardContent></Card>
      : <>
        <div className="grid min-w-0 gap-6 xl:grid-cols-3"><EdaTrendChart data={view.monthly} /><EdaWeeklyChart data={view.weekly} uplift={view.uplift} /><EdaWeekendChart data={view.weekend} /></div>
        <EdaHeatmap data={view.heatmap} />
        <EdaQuality store={store} />
        <p className="text-xs leading-5 text-muted-foreground">Charts use deterministic synthetic sales, not the original Kaggle observations. Quality counts describe the assumed complete dataset, not a measured audit. Monthly totals sum all items; daily averages are per item.</p>
      </>}
  </div>
}
