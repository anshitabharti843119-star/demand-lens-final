import { ChartNoAxesCombined, PackageOpen, ChartColumnIncreasing, Layers3 } from "lucide-react"

export const navigation = [
  { href: "/forecast", label: "Forecast", icon: ChartNoAxesCombined, phase: 1,
    subtitle: "A clearer picture of what comes next.", title: "Forecasting, with confidence.",
    description: "Daily demand predictions, an 80% confidence band, and an honest comparison against a simple baseline.",
    capabilities: ["14 & 30-day outlooks", "Model vs. baseline", "Confidence intervals"] },
  { href: "/restock", label: "Restock", icon: PackageOpen, phase: 2,
    subtitle: "Turn demand predictions into inventory decisions.", title: "The right stock. At the right time.",
    description: "A prioritized list of products to reorder, with concrete quantities based on forecast demand and your stock assumptions.",
    capabilities: ["Reorder quantities", "Stock assumptions", "CSV export"] },
  { href: "/eda", label: "EDA", icon: ChartColumnIncreasing, phase: 3,
    subtitle: "Understand the patterns behind your sales.", title: "See the bigger picture.",
    description: "Explore long-term trends, summer seasonality, and the weekend effect across all five stores.",
    capabilities: ["Sales trends", "Weekly seasonality", "Weekend uplift"] },
  { href: "/portfolio", label: "Portfolio", icon: Layers3, phase: 4,
    subtitle: "An honest benchmark across every store and item.", title: "Trust, backed by the whole picture.",
    description: "Compare model performance across all 250 series, including the cases where the baseline is the better choice.",
    capabilities: ["Model win rate", "Error distribution", "All 250 series"] },
] as const

export type DashboardRoute = (typeof navigation)[number]["href"]
