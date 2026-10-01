"use client"

import { useEffect, useState, useSyncExternalStore } from "react"
import { DemoMenu } from "@/components/demo-menu"
import { usePathname, useSearchParams } from "next/navigation"
import { useTheme } from "next-themes"
import { ChevronRight, Menu, Moon, Sun, Store } from "lucide-react"
import { AppSidebar } from "@/components/app-sidebar"
import { StoreItemSelector } from "@/components/store-item-selector"
import { navigation } from "@/lib/navigation"
import { readSelection } from "@/lib/selection"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { useBackendStatus } from "@/hooks/useBackendStatus"

const subscribe = () => () => {}
const tabletQuery = "(min-width: 768px) and (max-width: 1023px)"
const subscribeTablet = (callback: () => void) => {
  const media = window.matchMedia(tabletQuery)
  media.addEventListener("change", callback)
  return () => media.removeEventListener("change", callback)
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const mounted = useSyncExternalStore(subscribe, () => true, () => false)
  const dark = mounted && resolvedTheme === "dark"
  return <Button variant="ghost" size="icon" className="size-10" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} onClick={() => setTheme(dark ? "light" : "dark")}>
    {dark ? <Sun /> : <Moon />}
  </Button>
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname().replace(/\/$/, "")
  const params = useSearchParams()
  const { store, item } = readSelection(params)
  const [collapsed, setCollapsed] = useState<boolean | null>(null)
  const [open, setOpen] = useState(false)
  const [presentation, setPresentation] = useState(false)
  useEffect(() => {
    document.documentElement.classList.toggle("presentation-mode", presentation)
    return () => document.documentElement.classList.remove("presentation-mode")
  }, [presentation])
  const isTablet = useSyncExternalStore(subscribeTablet, () => window.matchMedia(tabletQuery).matches, () => false)
  const compact = collapsed ?? isTablet
  const title = navigation.find(route => route.href === pathname)?.label ?? "Data check"
  // Backend status
  const { backendOnline, seriesCount: backendSeriesCount } = useBackendStatus()
  return <div className="flex min-h-dvh">
    <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-card focus:p-4">Skip to content</a>
    <aside className={cn("app-sidebar sticky top-0 hidden h-dvh shrink-0 border-r md:block", compact ? "w-[72px]" : "w-60")}>
      <AppSidebar compact={compact} onToggle={() => setCollapsed(!compact)} />
    </aside>
    <div className="flex min-w-0 flex-1 flex-col">
      <header className="border-b bg-card">
        <div className="mx-auto flex h-[76px] max-w-[1280px] items-center justify-between gap-3 px-5 md:px-8 lg:px-10">
          <div className="flex items-center gap-3">
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger render={<Button variant="ghost" size="icon" className={cn("size-10", !presentation && "md:hidden")} aria-label="Open navigation" />}><Menu /></SheetTrigger>
              <SheetContent side="left" className="gap-0" aria-describedby={undefined}>
                <SheetHeader className="sr-only"><SheetTitle>DemandLens navigation</SheetTitle></SheetHeader>
                <AppSidebar onNavigate={() => setOpen(false)} />
              </SheetContent>
            </Sheet>
            <span className="hidden text-xs text-muted-foreground sm:inline">Workspace</span>
            <ChevronRight className="hidden size-3 text-muted-foreground sm:block" aria-hidden="true" />
            <span className="font-medium">{title}</span>
          </div>
          <div className="flex items-center gap-2 sm:gap-4">
            <DemoMenu presentation={presentation} onPresentation={() => setPresentation(value => !value)} />
            <Badge variant="outline" className="hidden sm:inline-flex"><Store data-icon="inline-start" />Store {store}<span className="px-1 text-muted-foreground">/</span>Item {item}</Badge>
            <div className="h-5 border-l" aria-hidden="true" />
            {/* Backend status chip */}
            {backendOnline ? (
              <Badge variant="default" className="bg-green-600 hover:bg-green-700 text-white">
                Backend online
              </Badge>
            ) : (
              <Badge variant="outline" className="text-muted-foreground">
                Static mode
              </Badge>
            )}
            <ThemeToggle />
          </div>
        </div>
        {pathname === "/forecast" && <StoreItemSelector />}
      </header>
      <main id="main-content" className="mx-auto flex w-full max-w-[1280px] flex-1 flex-col px-5 py-8 md:px-8 lg:px-10 lg:py-10" tabIndex={-1}>{children}</main>
      <footer className="mx-auto flex w-full max-w-[1280px] flex-wrap items-center justify-between gap-2 px-5 pb-6 text-[11px] text-muted-foreground md:px-8 lg:px-10">
        <span>DemandLens · Sales demand forecasting</span><span>250 series <span className="px-1">/</span> Prophet model · Kaggle Store-Item dataset</span>
      </footer>
    </div>
  </div>
}
