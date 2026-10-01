import type { Metadata } from "next"
import { EdaDashboard } from "@/components/eda/eda-dashboard"

export const metadata: Metadata = {
  title: "Exploratory data analysis",
  description: "Explore sales trends, weekly seasonality, and weekend uplift across five stores using deterministic mock data from 2013–2017.",
}
export default function EdaPage() { return <EdaDashboard /> }
