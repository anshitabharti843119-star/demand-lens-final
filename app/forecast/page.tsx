import type { Metadata } from "next"
import { ForecastDashboard } from "@/components/forecast/forecast-dashboard"

export const metadata: Metadata = { title: "Forecast", description: "Explore 14- and 30-day retail demand forecasts, confidence intervals, and honest model-versus-baseline metrics." }
export default function ForecastPage() { return <ForecastDashboard /> }
