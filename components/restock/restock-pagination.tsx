import { ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectGroup, SelectItem } from "@/components/ui/select"

const sizes = [25, 50, 100].map(size => ({ value: String(size), label: String(size) }))
interface Props { total: number; page: number; pageSize: number; onPage: (page: number) => void; onPageSize: (size: number) => void }
export function RestockPagination({ total, page, pageSize, onPage, onPageSize }: Props) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return <div className="flex flex-wrap items-center justify-between gap-4 border-t px-5 py-4 text-xs text-muted-foreground">
    <span>{total ? (page - 1) * pageSize + 1 : 0}–{Math.min(page * pageSize, total)} of {total} products</span>
    <div className="flex items-center gap-2"><label htmlFor="restock-page-size">Rows</label><Select items={sizes} value={String(pageSize)} onValueChange={value => { if (value) onPageSize(Number(value)) }}><SelectTrigger id="restock-page-size" size="sm"><SelectValue /></SelectTrigger><SelectContent><SelectGroup>{sizes.map(size => <SelectItem key={size.value} value={size.value}>{size.label}</SelectItem>)}</SelectGroup></SelectContent></Select><Button variant="outline" size="icon" aria-label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)}><ChevronLeft /></Button><span className="px-1">{page} / {pages}</span><Button variant="outline" size="icon" aria-label="Next page" disabled={page >= pages} onClick={() => onPage(page + 1)}><ChevronRight /></Button></div>
  </div>
}
