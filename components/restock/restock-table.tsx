"use client"

import { useSyncExternalStore } from "react"
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react"
import type { RestockRow } from "@/lib/types"
import { formatUnits, type RestockSort, type RestockSortKey } from "@/lib/restock-view"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { RestockCover, RestockPriority } from "./restock-status"

export const restockColumns: { key: RestockSortKey; label: string }[] = [
  { key: "item", label: "Product" }, { key: "store", label: "Store" }, { key: "current_stock", label: "Current stock" },
  { key: "forecast_demand", label: "Forecast demand" }, { key: "safety_stock", label: "Safety stock" }, { key: "restock_qty", label: "Restock qty" },
  { key: "days_of_cover", label: "Days of cover" }, { key: "priority", label: "Priority" },
]
interface Props { rows: RestockRow[]; horizon: number; sort: RestockSort; onSort: (key: RestockSortKey) => void; onOpen: (row: RestockRow) => void }

const mobileQuery = "(max-width: 767px)"
const subscribeMobile = (callback: () => void) => {
  const media = window.matchMedia(mobileQuery)
  media.addEventListener("change", callback)
  return () => media.removeEventListener("change", callback)
}
const getMobile = () => window.matchMedia(mobileQuery).matches
const getServerMobile = () => false

export function RestockTable({ rows, horizon, sort, onSort, onOpen }: Props) {
  const mobile = useSyncExternalStore(subscribeMobile, getMobile, getServerMobile)
  return <>
    {!mobile && <div className="hidden md:block [&_[data-slot=table-container]]:max-h-[620px] [&_[data-slot=table-container]]:overflow-auto">
      <Table aria-label="Products to restock" className="text-xs">
        <TableHeader className="sticky top-0 z-10 bg-card"><TableRow>{restockColumns.map(column => <TableHead key={column.key} scope="col" aria-sort={sort.key === column.key ? sort.direction === "asc" ? "ascending" : "descending" : "none"}><button className="flex min-h-12 items-center gap-1 py-2 text-left" onClick={() => onSort(column.key)}><span>{column.label}{column.key === "forecast_demand" && <span className="block text-[10px] font-normal text-muted-foreground">{horizon} days</span>}</span>{sort.key === column.key ? sort.direction === "asc" ? <ArrowUp className="size-3 shrink-0 text-primary" /> : <ArrowDown className="size-3 shrink-0 text-primary" /> : <ArrowUpDown className="size-3 shrink-0 text-muted-foreground" />}</button></TableHead>)}</TableRow></TableHeader>
        <TableBody>{rows.map(row => <TableRow key={row.series_id} data-series={row.series_id} className="cursor-pointer" onClick={() => onOpen(row)}>
          <TableCell><button className="min-h-10 font-medium underline-offset-4 hover:underline" aria-label={`View Item ${row.item}, Store ${row.store} calculation`} aria-haspopup="dialog" onClick={event => { event.stopPropagation(); onOpen(row) }}>Item {row.item}</button></TableCell>
          <TableCell>Store {row.store}</TableCell><TableCell>{formatUnits(row.current_stock)}</TableCell><TableCell>{formatUnits(row.forecast_demand)}</TableCell><TableCell>{formatUnits(row.safety_stock)}</TableCell><TableCell><strong className="text-sm text-primary">{formatUnits(row.restock_qty)}</strong></TableCell><TableCell><RestockCover row={row} horizon={horizon} /></TableCell><TableCell><RestockPriority priority={row.priority} /></TableCell>
        </TableRow>)}</TableBody>
      </Table>
    </div>}
    {mobile && <ul className="flex flex-col divide-y md:hidden" aria-label="Products to restock">{rows.map(row => <li key={row.series_id}>
      <button className="flex w-full flex-col gap-4 p-5 text-left hover:bg-muted/50" aria-haspopup="dialog" aria-label={`View Item ${row.item}, Store ${row.store} calculation`} onClick={() => onOpen(row)}>
        <div className="flex w-full items-start justify-between gap-4"><div><div className="font-semibold">Item {row.item}</div><div className="text-xs text-muted-foreground">Store {row.store}</div></div><div className="text-right"><div className="text-xl font-semibold text-primary">{formatUnits(row.restock_qty)}</div><div className="text-xs text-muted-foreground">units to order</div></div></div>
        <dl className="grid w-full grid-cols-2 gap-4 text-xs"><div><dt className="text-muted-foreground">Current stock</dt><dd className="mt-1">{formatUnits(row.current_stock)}</dd></div><div><dt className="text-muted-foreground">Forecast demand ({horizon}d)</dt><dd className="mt-1">{formatUnits(row.forecast_demand)}</dd></div><div><dt className="text-muted-foreground">Safety stock</dt><dd className="mt-1">{formatUnits(row.safety_stock)}</dd></div><div><dt className="mb-1 text-muted-foreground">Days of cover</dt><dd><RestockCover row={row} horizon={horizon} /></dd></div></dl>
        <RestockPriority priority={row.priority} />
      </button>
    </li>)}</ul>}
  </>
}

export function RestockMobileSort({ sort, onSort }: Pick<Props, "sort" | "onSort">) {
  return <div className="flex items-center gap-2 md:hidden"><Select items={restockColumns.map(column => ({ value: column.key, label: column.label }))} value={sort.key} onValueChange={key => { if (key && key !== sort.key) onSort(key as RestockSortKey) }}><SelectTrigger aria-label="Sort restock list" className="min-w-0 flex-1"><SelectValue /></SelectTrigger><SelectContent><SelectGroup>{restockColumns.map(column => <SelectItem key={column.key} value={column.key}>{column.label}</SelectItem>)}</SelectGroup></SelectContent></Select><Button variant="outline" size="icon" aria-label={sort.direction === "asc" ? "Sort descending" : "Sort ascending"} onClick={() => onSort(sort.key)}>{sort.direction === "asc" ? <ArrowUp /> : <ArrowDown />}</Button></div>
}
