import { Database } from "lucide-react"
import { edaQuality, formatEdaUnits, type EdaStoreFilter } from "@/lib/eda-view"

export function EdaQuality({ store }: { store: EdaStoreFilter }) {
  const quality = edaQuality(store)
  const metrics = [
    { label: "Rows", value: formatEdaUnits(quality.rows) },
    { label: "Date range", value: "Jan 1, 2013 – Dec 31, 2017" },
    { label: "Missing dates", value: String(quality.missing) },
    { label: "Duplicate rows", value: String(quality.duplicates) },
    { label: "Series", value: formatEdaUnits(quality.series) },
  ]
  return <section aria-labelledby="eda-quality-title" className="rounded-xl border bg-card p-5">
    <div className="mb-4 flex flex-wrap items-center gap-2"><Database className="size-4 text-muted-foreground" aria-hidden="true" /><h2 id="eda-quality-title">Data quality</h2><span className="text-xs text-muted-foreground">Expected complete dataset · simulated</span></div>
    <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-[1fr_2fr_1fr_1fr_1fr]">{metrics.map(metric => <div key={metric.label}><dt className="text-xs text-muted-foreground">{metric.label}</dt><dd className="mt-1 font-medium">{metric.value}</dd></div>)}</dl>
  </section>
}
