import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import type { RestockRow } from "@/lib/types"
import { formatCover } from "@/lib/restock-view"
import { cn } from "@/lib/utils"

export function RestockPriority({ priority }: { priority: RestockRow["priority"] }) {
  return <Badge variant="outline" className={cn("gap-1.5", priority === "HIGH" ? "border-danger/20 bg-danger/5 text-danger" : priority === "MEDIUM" ? "border-warning/20 bg-warning/5 text-warning" : "bg-muted text-muted-foreground")}><span className="size-1.5 rounded-full bg-current" aria-hidden="true" />{priority}</Badge>
}

export function RestockCover({ row, horizon }: { row: RestockRow; horizon: number }) {
  return <div className="flex min-w-20 flex-col gap-2"><span>{formatCover(row.days_of_cover)} days</span><Progress aria-label={`Item ${row.item}, Store ${row.store}: ${formatCover(row.days_of_cover)} days of cover out of ${horizon}`} value={Math.min(100, row.days_of_cover / horizon * 100)} className={cn("max-w-24 [&_[data-slot=progress-indicator]]:transition-none", row.priority === "HIGH" ? "[&_[data-slot=progress-indicator]]:bg-danger" : row.priority === "MEDIUM" ? "[&_[data-slot=progress-indicator]]:bg-warning" : "[&_[data-slot=progress-indicator]]:bg-muted-foreground")} /></div>
}
