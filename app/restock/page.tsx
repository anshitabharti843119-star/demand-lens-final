import type { Metadata } from "next"
import { RestockDashboard } from "@/components/restock/restock-dashboard"

export const metadata: Metadata = { title: "Restock", description: "Plan replenishment with forecast demand, adjustable stock assumptions, and a prioritized restock list." }
export default function RestockPage() { return <RestockDashboard /> }
