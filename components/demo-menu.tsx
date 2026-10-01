"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Play, Monitor, Check } from "lucide-react"
import { getRestockInputs } from "@/lib/data"
import { computeRestock } from "@/lib/restock"
import { defaultRestockOptions } from "@/lib/restock-view"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuGroup, DropdownMenuLabel, DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu"

export function DemoMenu({ presentation, onPresentation }: { presentation: boolean; onPresentation: () => void }) {
  const router = useRouter()
  const [error, setError] = useState(false)
  const [busy, setBusy] = useState(false)
  async function urgent() {
    setBusy(true); setError(false)
    try {
      const row = computeRestock(await getRestockInputs(), defaultRestockOptions).find(row => row.priority === "HIGH" && row.restock_qty > 0)
      router.push(row ? `/restock?store=${row.store}&item=${row.item}&h=30&priority=HIGH&demo=urgent` : "/restock")
    } catch { setError(true) }
    finally { setBusy(false) }
  }
  return <div className="flex items-center gap-2"><DropdownMenu><DropdownMenuTrigger render={<Button variant="outline" size="sm" aria-label="Demo mode" disabled={busy} />}><Play data-icon="inline-start" /><span className="hidden sm:inline">Demo mode</span></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuGroup><DropdownMenuLabel>Demo presets</DropdownMenuLabel><DropdownMenuItem onClick={() => router.push("/forecast?store=1&item=12&h=30&mode=backtest")}>Model wins clearly</DropdownMenuItem><DropdownMenuItem onClick={() => router.push("/forecast?store=1&item=1&h=30&mode=backtest")}>Baseline wins (honest case)</DropdownMenuItem><DropdownMenuItem onClick={() => void urgent()}>Urgent restock</DropdownMenuItem></DropdownMenuGroup><DropdownMenuSeparator /><DropdownMenuGroup><DropdownMenuItem onClick={onPresentation}><Monitor />{presentation ? "Exit presentation mode" : "Presentation mode"}{presentation && <Check />}</DropdownMenuItem></DropdownMenuGroup></DropdownMenuContent></DropdownMenu>{error && <button onClick={() => void urgent()} className="text-xs text-danger" role="alert">Retry demo</button>}</div>
}
