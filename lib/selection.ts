import type { Horizon, Mode } from "@/lib/types"

export interface Selection { store: number; item: number; horizon: Horizon; mode: Mode }
export const defaultSelection: Selection = { store: 1, item: 12, horizon: 30, mode: "backtest" }

function validNumber(value: string | null, max: number, fallback: number) {
  const number = Number(value)
  return Number.isInteger(number) && number >= 1 && number <= max ? number : fallback
}

export function readSelection(params: Pick<URLSearchParams, "get">): Selection {
  return {
    store: validNumber(params.get("store"), 5, defaultSelection.store),
    item: validNumber(params.get("item"), 50, defaultSelection.item),
    horizon: params.get("h") === "14" ? 14 : 30,
    mode: params.get("mode") === "future" ? "future" : "backtest",
  }
}

export function selectionQuery(selection: Selection, existing = "") {
  const params = new URLSearchParams(existing)
  params.set("store", String(selection.store))
  params.set("item", String(selection.item))
  params.set("h", String(selection.horizon))
  params.set("mode", selection.mode)
  return params.toString()
}
