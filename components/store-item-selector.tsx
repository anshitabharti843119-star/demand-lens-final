"use client"

import { useSearchParams } from "next/navigation"
import { CalendarDays, SlidersHorizontal } from "lucide-react"
import { readSelection, selectionQuery, type Selection } from "@/lib/selection"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Combobox, ComboboxContent, ComboboxEmpty, ComboboxInput, ComboboxItem, ComboboxList } from "@/components/ui/combobox"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"

const stores = Array.from({ length: 5 }, (_, i) => ({ value: String(i + 1), label: `Store ${i + 1}` }))
const items = Array.from({ length: 50 }, (_, i) => `Item ${i + 1}`)

export function StoreItemSelector() {
  const params = useSearchParams()
  const selection = readSelection(params)
  function update(patch: Partial<Selection>) {
    const current = new URLSearchParams(window.location.search)
    const query = selectionQuery({ ...readSelection(current), ...patch }, current.toString())
    window.history.pushState(null, "", `${window.location.pathname}?${query}`)
  }
  return (
    <section aria-label="Forecast selections" className="selector-controls border-t bg-card">
      <div className="mx-auto flex max-w-[1280px] flex-wrap items-end gap-6 px-5 py-5 md:px-8 lg:px-10">
        <SlidersHorizontal className="mb-3 hidden size-4 text-muted-foreground xl:block" aria-hidden="true" />
        <FieldGroup className="grid flex-1 grid-cols-2 gap-4 sm:flex sm:flex-row sm:flex-wrap sm:items-end sm:gap-6">
          <Field className="gap-2 sm:w-36">
            <FieldLabel htmlFor="store-select">Store</FieldLabel>
            <Select items={stores} value={String(selection.store)} onValueChange={value => { if (value) update({ store: Number(value) }) }}>
              <SelectTrigger id="store-select" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent><SelectGroup>{stores.map(store => <SelectItem key={store.value} value={store.value}>{store.label}</SelectItem>)}</SelectGroup></SelectContent>
            </Select>
          </Field>
          <Field className="gap-2 sm:w-40">
            <FieldLabel htmlFor="item-select">Item</FieldLabel>
            <Combobox items={items} value={`Item ${selection.item}`} onValueChange={value => { if (value) update({ item: Number(value.replace("Item ", "")) }) }}>
              <ComboboxInput id="item-select" aria-label="Search item" placeholder="Search items…" />
              <ComboboxContent><ComboboxEmpty>No matching items.</ComboboxEmpty><ComboboxList>{(item: string) => <ComboboxItem key={item} value={item}>{item}</ComboboxItem>}</ComboboxList></ComboboxContent>
            </Combobox>
          </Field>
          <Field className="gap-2 sm:w-auto">
            <FieldLabel id="horizon-label">Horizon</FieldLabel>
            <ToggleGroup aria-labelledby="horizon-label" value={[String(selection.horizon)]} onValueChange={value => { if (value[0]) update({ horizon: value[0] === "14" ? 14 : 30 }) }} spacing={0}>
              <ToggleGroupItem value="14">14 days</ToggleGroupItem><ToggleGroupItem value="30">30 days</ToggleGroupItem>
            </ToggleGroup>
          </Field>
          <Field className="gap-2 sm:w-auto">
            <FieldLabel id="mode-label">Mode</FieldLabel>
            <ToggleGroup aria-labelledby="mode-label" value={[selection.mode]} onValueChange={value => { if (value[0]) update({ mode: value[0] === "future" ? "future" : "backtest" }) }} spacing={0}>
              <ToggleGroupItem value="backtest">Backtest</ToggleGroupItem><ToggleGroupItem value="future">Future</ToggleGroupItem>
            </ToggleGroup>
          </Field>
        </FieldGroup>
        <span className="mb-3 hidden items-center gap-2 text-xs text-muted-foreground 2xl:flex"><CalendarDays className="size-3.5" aria-hidden="true" />{selection.mode === "backtest" ? "Dec 2017" : "Jan 2018"}</span>
      </div>
    </section>
  )
}
