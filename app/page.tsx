"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { readSelection, selectionQuery } from "@/lib/selection"

export default function Home() {
  const router = useRouter()
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    router.replace(`/forecast?${selectionQuery(readSelection(params), params.toString())}`)
  }, [router])
  return <p className="p-8 text-muted-foreground">Opening your workspace… <Link className="text-primary underline" href="/forecast">Go to Forecast</Link></p>
}
