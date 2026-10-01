import { Skeleton } from "@/components/ui/skeleton"

export function PageSkeleton() {
  return <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 p-6 md:p-10" role="status" aria-label="Loading workspace">
    <span className="sr-only">Loading workspace…</span>
    <Skeleton className="h-8 w-40" /><Skeleton className="h-5 w-64 max-w-full" />
    <Skeleton className="h-24 w-full rounded-xl" /><Skeleton className="h-96 w-full rounded-xl" />
  </div>
}
