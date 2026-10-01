"use client"

import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"
import { Activity, Database, PanelLeftClose, PanelLeftOpen } from "lucide-react"
import { navigation } from "@/lib/navigation"
import { readSelection, selectionQuery } from "@/lib/selection"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

export function Brand({ compact = false }: { compact?: boolean }) {
  return <div className="flex items-center gap-3 whitespace-nowrap">
    <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Activity className="size-5" strokeWidth={2.2} aria-hidden="true" /></span>
    {!compact && <span className="text-[18px] font-semibold tracking-[-0.7px]">DemandLens<span className="text-primary">.</span></span>}
  </div>
}

export function AppSidebar({ compact = false, onToggle, onNavigate }: {
  compact?: boolean; onToggle?: () => void; onNavigate?: () => void
}) {
  const pathname = usePathname().replace(/\/$/, "")
  const params = useSearchParams()
  const query = selectionQuery(readSelection(params))
  return (
    <div className="flex h-full flex-col bg-card">
      <div className={cn("flex h-[76px] shrink-0 items-center border-b px-6", compact && "justify-center px-0")}><Brand compact={compact} /></div>
      <div className={cn("px-6 pb-3 pt-8 text-[10px] font-semibold tracking-[0.14em] text-muted-foreground", compact && "px-0 text-center")}>
        {compact ? "···" : "WORKSPACE"}
      </div>
      <nav aria-label="Main navigation" className="flex flex-col gap-2 px-3">
        {navigation.map(({ href, label, icon: Icon }) => {
          const active = pathname === href
          return <Tooltip key={href}>
            <TooltipTrigger render={<Link href={`${href}?${query}`} onClick={onNavigate} aria-label={label} aria-current={active ? "page" : undefined}
              className={cn("flex min-h-11 items-center gap-3 rounded-lg px-3 font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground", active && "bg-accent text-primary hover:bg-accent hover:text-primary", compact && "justify-center px-0")} />}>
              <Icon className="size-[18px] shrink-0" aria-hidden="true" />
              {!compact && <><span>{label}</span>{active && <span className="ml-auto size-1.5 rounded-full bg-primary" />}</>}
            </TooltipTrigger>
            {compact && <TooltipContent side="right">{label}</TooltipContent>}
          </Tooltip>
        })}
      </nav>
      <div className="mt-auto">
        {!compact && <div className="mx-5 mb-5 flex flex-col gap-3 rounded-lg border bg-background p-3">
          <div className="flex items-center gap-2 text-xs font-medium"><Database className="size-3.5 text-muted-foreground" aria-hidden="true" /> Dataset</div>
          <p className="text-xs leading-5 text-muted-foreground">Data: Kaggle Store Item Demand<br />Test window: Dec 2017</p>
          <span className="flex items-center gap-2 text-[11px] text-muted-foreground"><span className="size-1.5 rounded-full bg-emerald-500" />Pipeline data</span>
        </div>}
        <Separator />
        <div className={cn("flex min-h-16 items-center justify-between px-5", compact && "justify-center px-0")}>
          {!compact && <span className="text-xs text-muted-foreground">DemandLens <span className="ml-1 text-[10px]">v0.1</span></span>}
          {onToggle && <Button variant="ghost" size="icon" onClick={onToggle} aria-label={compact ? "Expand sidebar" : "Collapse sidebar"}>
            {compact ? <PanelLeftOpen /> : <PanelLeftClose />}
          </Button>}
        </div>
      </div>
    </div>
  )
}
