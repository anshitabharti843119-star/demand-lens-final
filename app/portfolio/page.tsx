import type { Metadata } from "next"
import { PortfolioDashboard } from "@/components/portfolio/portfolio-dashboard"

export const metadata: Metadata = {
  title: "Portfolio",
  description: "Compare model and baseline errors across all 250 retail series with win-rate, improvement distributions, and transparent backtest rankings.",
}
export default function PortfolioPage() { return <PortfolioDashboard /> }
