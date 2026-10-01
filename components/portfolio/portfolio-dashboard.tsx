"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { getPortfolio } from "@/lib/data"
import { selectPortfolio, type PortfolioStoreFilter } from "@/lib/portfolio-view"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldLabel } from "@/components/ui/field"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { PortfolioMetrics } from "./portfolio-metrics"
import { PortfolioHistogram } from "./portfolio-histogram"
import { PortfolioScatter } from "./portfolio-scatter"
import { PortfolioRanking } from "./portfolio-ranking"

const stores = [{ value: "all", label: "All stores" }, ...[1, 2, 3, 4, 5].map(store => ({ value: String(store), label: `Store ${store}` }))]

export function PortfolioDashboard() {
  const { data, error, mutate } = useSWR("portfolio", getPortfolio, { revalidateOnFocus: false })
  const [store, setStore] = useState<PortfolioStoreFilter>("all")
  const view = useMemo(() => data ? selectPortfolio(data, store) : null, [data, store])
  return <div className="flex flex-col gap-6">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex flex-col gap-2"><h1>Model vs baseline across all series</h1><p className="text-muted-foreground">Measured on the held-out Dec 2017 test window</p><div className="flex flex-wrap items-center gap-2"><Badge variant="outline">Prophet model · Dec 2017 hold-out</Badge><span className="text-xs text-muted-foreground">30-day backtest · {store === "all" ? "All 5 stores" : `Store ${store}`}</span></div></div>
      <Field className="w-44"><FieldLabel htmlFor="portfolio-store">Store</FieldLabel><Select items={stores} value={String(store)} onValueChange={value => { if (value !== null) setStore(value === "all" ? "all" : Number(value)) }}><SelectTrigger id="portfolio-store" className="min-h-11 w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup>{stores.map(option => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectGroup></SelectContent></Select></Field>
    </header>
    {error ? <Card><CardContent><Empty role="alert"><EmptyHeader><EmptyTitle>Unable to load portfolio</EmptyTitle><EmptyDescription>Please retry loading the model comparison.</EmptyDescription></EmptyHeader><Button variant="outline" onClick={() => { void mutate() }}>Retry</Button></Empty></CardContent></Card>
      : !view ? <PortfolioSkeleton />
      : !view.count ? <Card><CardContent><Empty><EmptyHeader><EmptyTitle>No series for this store</EmptyTitle><EmptyDescription>Choose another store or retry loading the portfolio.</EmptyDescription></EmptyHeader><div className="flex gap-2"><Button variant="outline" onClick={() => setStore("all")}>All stores</Button><Button variant="outline" onClick={() => { void mutate() }}>Retry</Button></div></Empty></CardContent></Card>
      : <>
        <PortfolioMetrics view={view} />
        <div className="grid min-w-0 gap-6 xl:grid-cols-2"><PortfolioHistogram bins={view.histogram} /><PortfolioScatter rows={view.rows} max={view.scatterMax} /></div>
        <div className="grid min-w-0 gap-6 xl:grid-cols-2"><PortfolioRanking rows={view.top} /><PortfolioRanking rows={view.worst} worst /></div>
        <Card><CardHeader><CardTitle>An honest comparison</CardTitle><CardDescription>We show series where the model loses too. Metrics use the same test window and the same series for model and baseline, and no test data is used in training.</CardDescription></CardHeader><CardContent><p className="text-xs leading-5 text-muted-foreground">These are deterministic synthetic series and simulated predictions, not a trained production model. Scores come from the existing 30-day backtest data; the statement above describes the intended real-data evaluation protocol.</p></CardContent></Card>
      </>}
  </div>
}

function PortfolioSkeleton() {
  return <div className="flex flex-col gap-6" role="status" aria-label="Loading portfolio">
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map(index => <Card key={index}><CardHeader><Skeleton className="h-8 w-36" /></CardHeader><CardContent className="flex flex-col gap-2"><Skeleton className="h-9 w-24" /><Skeleton className="h-4 w-40" /></CardContent></Card>)}</div>
    <div className="grid gap-6 xl:grid-cols-2">{[0, 1].map(index => <Card key={index}><CardHeader><Skeleton className="h-6 w-48" /><Skeleton className="h-10 w-full" /></CardHeader><CardContent><Skeleton className="h-80 w-full" /></CardContent></Card>)}</div>
  </div>
}
