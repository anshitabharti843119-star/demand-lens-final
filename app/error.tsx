"use client"

import { RefreshCw, TriangleAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyContent, EmptyMedia } from "@/components/ui/empty"

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <Empty className="min-h-96 border bg-card">
    <EmptyHeader><EmptyMedia variant="icon"><TriangleAlert /></EmptyMedia><EmptyTitle>Something didn&apos;t load</EmptyTitle><EmptyDescription>Your selection is safe in the URL. Please try loading this view again.</EmptyDescription></EmptyHeader>
    <EmptyContent><Button variant="outline" onClick={reset}><RefreshCw data-icon="inline-start" />Try again</Button></EmptyContent>
  </Empty>
}
