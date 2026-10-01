import { ArrowRight, Boxes, CalendarDays, Database, Info, Store } from "lucide-react"
import { navigation, type DashboardRoute } from "@/lib/navigation"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"

export function PhasePlaceholder({ route }: { route: DashboardRoute }) {
  const page = navigation.find(item => item.href === route)!
  const Icon = page.icon
  return <div className="flex flex-col gap-7">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex flex-col gap-2"><h1>{page.label === "EDA" ? "Exploratory data analysis" : page.label === "Restock" ? "Restock list" : page.label}</h1><p className="text-muted-foreground">{page.subtitle}</p></div>
      <Badge variant="outline"><span className="size-1.5 rounded-full bg-warning" />Mock data</Badge>
    </div>
    <div className="grid grid-cols-2 gap-y-5 rounded-xl border bg-card py-5 sm:grid-cols-4">
      {[{ label: "Stores", value: "5", icon: Store }, { label: "Items per store", value: "50", icon: Boxes }, { label: "Demand series", value: "250", icon: Database }, { label: "Dataset period", value: "2013–2017", icon: CalendarDays }].map(({ label, value, icon: StatIcon }, i) =>
        <div key={label} className={cn("flex flex-col gap-2 px-5 md:px-6", i % 2 === 1 && "border-l", i === 2 && "sm:border-l")}>
          <span className="flex items-center gap-2 text-xs text-muted-foreground"><StatIcon className="size-3.5" aria-hidden="true" />{label}</span><span className="text-xl font-semibold tracking-tight">{value}</span>
        </div>)}
    </div>
    <Card className="gap-0 overflow-hidden py-0 shadow-none">
      <CardHeader className="flex flex-row items-center justify-between border-b px-5 py-4 sm:px-6">
        <CardTitle>{page.label === "Forecast" ? "Demand forecast" : page.label === "Restock" ? "Restock planning" : page.label === "EDA" ? "Sales patterns" : "Model performance"}</CardTitle>
        <Badge variant="secondary">Coming in Phase {page.phase}</Badge>
      </CardHeader>
      <CardContent className="flex min-h-[350px] items-center justify-center p-5 sm:min-h-[368px]">
        <Empty className="max-w-lg border-0 p-0">
          <EmptyHeader className="max-w-md gap-4">
            <div className="mb-2 flex size-16 items-center justify-center rounded-2xl border border-primary/10 bg-accent"><Icon className="size-7 text-primary" strokeWidth={1.5} aria-hidden="true" /></div>
            <EmptyTitle>{page.title}</EmptyTitle>
            <EmptyDescription>{page.description}</EmptyDescription>
          </EmptyHeader>
          <p className="mt-1 flex items-center gap-2 text-xs text-muted-foreground"><span className="size-1.5 rounded-full bg-history" />Your workspace is ready. This view is up next.</p>
        </Empty>
      </CardContent>
      <CardFooter className="flex flex-wrap items-center justify-center gap-x-6 gap-y-3 border-t bg-background px-5 py-4 text-xs text-muted-foreground">
        {page.capabilities.map(label => <span key={label} className="flex items-center gap-2"><ArrowRight className="size-3 text-history" aria-hidden="true" />{label}</span>)}
      </CardFooter>
    </Card>
    <Card className="gap-0 bg-transparent shadow-none">
      <CardHeader className="flex flex-row items-start gap-3">
        <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="flex flex-col gap-1.5"><CardTitle>A transparent foundation</CardTitle><CardDescription>{route === "/restock" ? "Stock levels are simulated (dataset has no inventory data). " : "You’re viewing a foundation build with deterministic, simulated sales data. "}No live predictions are shown yet. All analytics will use the same held-out test window.</CardDescription></div>
      </CardHeader>
      <CardContent className="ml-7 flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted-foreground">
        <span>Training ends <span className="ml-2 font-medium text-foreground">Nov 30, 2017</span></span>
        <span>Test window <span className="ml-2 font-medium text-foreground">Dec 2017</span></span>
        <span>Future outlook <span className="ml-2 font-medium text-foreground">Jan 2018</span></span>
      </CardContent>
    </Card>
  </div>
}
