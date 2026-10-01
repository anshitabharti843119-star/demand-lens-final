"use client"

import type { ReactNode } from "react"
import { Info } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Button } from "@/components/ui/button"
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription } from "@/components/ui/empty"

export function EdaChartCard({ title, insight, info, children }: { title: string; insight: string; info: string; children: ReactNode }) {
  return <Card className="min-w-0 gap-4">
    <CardHeader className="gap-2">
      <div className="flex items-center justify-between gap-2">
        <CardTitle>{title}</CardTitle>
        <Tooltip>
          <TooltipTrigger render={<Button variant="ghost" size="icon" aria-label={`About ${title.toLowerCase()}`} />}><Info /></TooltipTrigger>
          <TooltipContent className="max-w-72">{info}</TooltipContent>
        </Tooltip>
      </div>
      <CardDescription className="min-h-10">{insight}</CardDescription>
    </CardHeader>
    <CardContent className="min-w-0">{children}</CardContent>
  </Card>
}

export function EdaChartEmpty() {
  return <Empty className="min-h-72"><EmptyHeader><EmptyTitle>No observations</EmptyTitle><EmptyDescription>No data is available for this chart and store.</EmptyDescription></EmptyHeader></Empty>
}
