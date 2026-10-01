"use client"

import Link from "next/link"
import { useMemo } from "react"
import useSWR from "swr"
import { ArrowUpRight } from "lucide-react"
import { getRestockInputs } from "@/lib/data"
import { computeRestock } from "@/lib/restock"
import { defaultRestockOptions, formatCover, formatUnits } from "@/lib/restock-view"
import type { Horizon } from "@/lib/types"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { RestockPriority } from "@/components/restock/restock-status"

export function RestockPreview({ store, horizon }: { store: number; horizon: Horizon }) {
  const { data, error, mutate } = useSWR("restock-inputs", getRestockInputs, { revalidateOnFocus: false })
  const rows = useMemo(() => data ? computeRestock(data, { ...defaultRestockOptions, horizon }).filter(row => row.store === store && row.restock_qty > 0).slice(0, 5) : [], [data, store, horizon])
  return <Card><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>Restock at a glance</CardTitle><CardDescription className="mt-1">Store {store} · next {horizon} days · most urgent first</CardDescription></div><Link href={`/restock?store=${store}&h=${horizon}`} className="inline-flex items-center gap-1 text-xs font-medium text-primary">View full restock list<ArrowUpRight className="size-3.5" /></Link></div></CardHeader><CardContent>
    {error ? <div role="alert" className="flex flex-wrap items-center gap-3">Restock preview could not load.<Button variant="outline" onClick={() => void mutate()}>Retry</Button></div> : !data ? <Skeleton className="h-24 w-full" /> : !rows.length ? <p className="py-6 text-muted-foreground">Nothing to restock for this store with the default assumptions.</p> : <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{rows.map(row => <li key={row.series_id}><Link href={`/forecast?store=${store}&item=${row.item}&h=${horizon}&mode=future`} className="flex h-full flex-col gap-3 rounded-lg border p-4 transition-colors hover:bg-muted"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">Item {row.item}</span><RestockPriority priority={row.priority} /></div><p className="text-2xl font-semibold text-primary">{formatUnits(row.restock_qty)}<span className="ml-1 text-xs font-normal text-muted-foreground">units</span></p><p className="text-xs text-muted-foreground">{formatCover(row.days_of_cover)} days of cover</p></Link></li>)}</ul>}
    <p className="mt-4 text-xs leading-5 text-muted-foreground">Current stock is simulated (no stock data in dataset). 95% service level · 3-day lead time · stock multiplier 1×.</p>
  </CardContent></Card>
}
