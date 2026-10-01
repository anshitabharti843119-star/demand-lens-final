import type { Metadata } from "next"
import { DataCheck } from "@/components/data-check"
import { notFound } from "next/navigation"

export const metadata: Metadata = { title: "Developer data check", robots: { index: false, follow: false } }
export default function DataCheckPage() {
  if (process.env.NODE_ENV === "production") notFound()
  return <DataCheck />
}
