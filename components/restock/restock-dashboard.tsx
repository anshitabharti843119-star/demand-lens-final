"use client"

import { useEffect, useMemo, useState } from "react"
import dynamic from "next/dynamic"
import { useSearchParams } from "next/navigation"
import { readSelection } from "@/lib/selection"
import useSWR from "swr"
import { Download, Info, Package, Layers, AlertTriangle, Clock, Upload, FileText, Trash2 } from "lucide-react"
import { getRestockInputs } from "@/lib/data"
import { computeRestock, type RestockOptions } from "@/lib/restock"
import { defaultRestockOptions, defaultRestockFilters, defaultRestockSort, filterSortRestock, summarizeRestock, downloadRestockCsv, formatUnits, formatCover, type RestockFilters, type RestockSortKey } from "@/lib/restock-view"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { RestockControls } from "./restock-controls"
import { RestockTable, RestockMobileSort } from "./restock-table"
import { RestockPagination } from "./restock-pagination"
import { useBackendStatus } from "@/hooks/useBackendStatus"
import { uploadStock, getStock, clearStock, whatif, restock, type ApiError, type RestockResponse, type StockState, type WhatIfResponse } from "@/lib/api"
import { applyUploadedStock, clearSavedStockUpload, loadSavedStockUpload, MAX_STOCK_CSV_BYTES, parseStockCsv, saveStockUpload, stockNoteText, stockTemplateCsv, type SavedStockUpload } from "@/lib/stock-upload"
const RestockSheet = dynamic(() => import("./restock-sheet").then(module => module.RestockSheet), { ssr: false })

export function RestockDashboard() {
  const params = useSearchParams()
  return <RestockWorkspace key={params.toString()} query={params.toString()} />
}

function RestockWorkspace({ query }: { query: string }) {
  const params = new URLSearchParams(query)
  const selection = readSelection(params)
  const urgent = params.get("demo") === "urgent"
  const { data, error, mutate } = useSWR("restock-inputs", getRestockInputs, { revalidateOnFocus: false })
  
  // Backend status
  const { backendOnline } = useBackendStatus()
  
  // Stock state
  const { data: stockResult, mutate: mutateStock } = useSWR(
    backendOnline ? "stock" : null,
    getStock,
    { revalidateOnFocus: false, revalidateIfStale: false },
  )
  const stockData: StockState | undefined = stockResult?.ok === true ? stockResult.data : undefined
  const [savedStock, setSavedStock] = useState<SavedStockUpload | null>(null)
  useEffect(() => {
    setSavedStock(loadSavedStockUpload())
  }, [])
  const [useUploadedStock, setUseUploadedStock] = useState(false)
  const [options, setOptions] = useState(() => ({ ...defaultRestockOptions, horizon: selection.horizon }))
  const [filters, setFilters] = useState(() => ({
    ...defaultRestockFilters,
    store: params.has("store") ? String(selection.store) : "all",
    priority: urgent ? "HIGH" : "all",
    search: params.has("item") ? String(selection.item) : "",
  }))
  const apiStoreFilter = filters.store === "all" ? undefined : Number(filters.store)
  const apiPriorityFilter = filters.priority === "all"
    ? undefined
    : filters.priority as "HIGH" | "MEDIUM" | "LOW"
  const [sort, setSort] = useState(defaultRestockSort)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [selectedId, setSelectedId] = useState<string | null>(() => urgent ? `S${selection.store}_I${selection.item}` : null)
  const effectiveInputs = useMemo(() => {
    if (!data || !useUploadedStock || !savedStock) return data
    return applyUploadedStock(data, savedStock.rows)
  }, [data, savedStock, useUploadedStock])
  const computed = useMemo(() => {
    try { return { rows: effectiveInputs ? computeRestock(effectiveInputs, options) : [], error: null } }
    catch { return { rows: [], error: "The restock data could not be calculated. Please retry." } }
  }, [effectiveInputs, options])
  const useUploadedResult = backendOnline && useUploadedStock && stockData?.active === true && !savedStock
  const restockRequestOptions = useMemo(() => ({
    horizon: options.horizon,
    service_level: options.serviceLevel,
    lead_time: options.leadTime,
    stock_multiplier: options.stockMultiplier,
    ...(apiStoreFilter !== undefined ? { store: apiStoreFilter } : {}),
    ...(apiPriorityFilter !== undefined ? { priority: apiPriorityFilter } : {}),
    only_restock: true,
    use_uploaded_stock: true,
  }), [options.horizon, options.serviceLevel, options.leadTime, options.stockMultiplier, apiStoreFilter, apiPriorityFilter])
  const uploadedRequest = useMemo(() => ({
    ...restockRequestOptions,
  }), [restockRequestOptions])
  const {
    data: uploadedRestock,
    error: uploadedRestockError,
    isLoading: uploadedRestockLoading,
    mutate: mutateUploadedRestock,
  } = useSWR<RestockResponse, Error>(
    useUploadedResult ? `uploaded-restock:${JSON.stringify(uploadedRequest)}` : null,
    async () => {
      const response = await restock(uploadedRequest)
      if (response.ok === true) return response.data
      throw new Error(response.error)
    },
    { revalidateOnFocus: false },
  )
  const resultRows = useUploadedResult ? uploadedRestock?.rows ?? [] : computed.rows
  const rows = useMemo(() => filterSortRestock(resultRows, filters, sort), [resultRows, filters, sort])
  const summary = useMemo(() => summarizeRestock(rows), [rows])
  const currentPage = Math.min(page, Math.max(1, Math.ceil(rows.length / pageSize)))
  const visibleRows = rows.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  const selected = resultRows.find(row => row.series_id === selectedId)
  const loading = (!data && !error) || (useUploadedResult && uploadedRestockLoading)
  const failed = error || (useUploadedResult && uploadedRestockError?.message) || computed.error
  const [stockUploadError, setStockUploadError] = useState<ApiError | null>(null)
  // Stock file handlers
  const handleStockUpload = async (file: File) => {
    setStockUploadError(null)
    if (file.size > MAX_STOCK_CSV_BYTES) {
      setStockUploadError({ ok: false, error: "CSV file must be 1 MB or smaller", errors: [{ line: 0, message: "CSV file must be 1 MB or smaller" }] })
      return
    }
    let csvText: string
    try {
      csvText = await file.text()
    } catch {
      setStockUploadError({ ok: false, error: "Could not read the selected CSV file." })
      return
    }
    const parsed = parseStockCsv(csvText)
    if (parsed.ok === false) {
      setStockUploadError({ ok: false, error: "Please fix the CSV validation errors.", errors: parsed.errors })
      return
    }
    const upload: SavedStockUpload = {
      uploaded_at: new Date().toISOString(),
      source_filename: file.name,
      rows: parsed.rows,
      row_count: parsed.count,
    }
    setSavedStock(upload)
    saveStockUpload(upload)

    if (backendOnline) {
      const mirrored = await uploadStock(file)
      if (mirrored.ok === false) setStockUploadError(mirrored)
      await mutateStock()
      await mutateUploadedRestock()
    }
  }
  
  const handleClearStock = async () => {
    setStockUploadError(null)
    clearSavedStockUpload()
    setSavedStock(null)
    setUseUploadedStock(false)
    if (backendOnline) {
      const result = await clearStock()
      if (result.ok === false) setStockUploadError(result)
      await mutateStock()
      await mutateUploadedRestock()
    }
  }

  const downloadTemplate = () => {
    if (!data) return
    const objectUrl = URL.createObjectURL(new Blob([stockTemplateCsv(data)], { type: "text/csv;charset=utf-8" }))
    const link = document.createElement("a")
    link.href = objectUrl
    link.download = "stock_template.csv"
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
  }
  
  // What-if state
  const [whatIfUplift, setWhatIfUplift] = useState(0)
  const [whatIfStartDay, setWhatIfStartDay] = useState(1)
  const [whatIfEndDay, setWhatIfEndDay] = useState(30)
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResponse | null>(null)
  const [whatIfLoading, setWhatIfLoading] = useState(false)
  const [whatIfError, setWhatIfError] = useState<string | null>(null)
  
  const handleWhatIf = async () => {
    if (!backendOnline) return
    setWhatIfLoading(true)
    setWhatIfError(null)
    const result = await whatif({
      scenario: { demand_uplift_pct: whatIfUplift, start_day: whatIfStartDay, end_day: whatIfEndDay },
      options: {
        horizon: options.horizon,
        service_level: options.serviceLevel,
        lead_time: options.leadTime,
        stock_multiplier: options.stockMultiplier,
        ...(apiStoreFilter !== undefined ? { store: apiStoreFilter } : {}),
        ...(apiPriorityFilter !== undefined ? { priority: apiPriorityFilter } : {}),
        only_restock: false,
        use_uploaded_stock: useUploadedStock && stockData?.active === true,
      },
    })
    if (result.ok === true) setWhatIfResult(result.data)
    else if (result.ok === false) setWhatIfError(result.error)
    setWhatIfLoading(false)
  }
  
  function changeOptions(patch: Partial<RestockOptions>) { setOptions(previous => ({ ...previous, ...patch })); setPage(1) }
  function changeFilters(patch: Partial<RestockFilters>) { setFilters(previous => ({ ...previous, ...patch })); setPage(1) }
  function changeSort(key: RestockSortKey) { setSort(previous => ({ key, direction: previous.key === key && previous.direction === "asc" ? "desc" : "asc" })); setPage(1) }
  function reset() { setOptions(defaultRestockOptions); setFilters(defaultRestockFilters); setSort(defaultRestockSort); setPage(1); setPageSize(25); setSelectedId(null) }
  const stockNote = useUploadedResult
    ? (uploadedRestock?.stock_source === "uploaded"
      ? `Using uploaded stock for ${uploadedRestock.rows.length} series (others simulated)`
      : uploadedRestock?.stock_source?.startsWith("mixed")
        ? `Using uploaded stock for ${uploadedRestock.stock_source.match(/\d+/)?.[0] ?? stockData.row_count ?? 0} series (others simulated)`
        : `Using uploaded stock for ${stockData.row_count ?? 0} series (others simulated)`)
    : stockNoteText(useUploadedStock && !!savedStock, savedStock?.row_count ?? 0)
  
  const metrics = [
    { label: "Products to restock", value: formatUnits(summary.products), icon: Package },
    { label: "Total units to order", value: formatUnits(summary.units), icon: Layers },
    { label: "HIGH priority", value: formatUnits(summary.high), icon: AlertTriangle },
    { label: "Avg days of cover", value: `${formatCover(summary.cover)} days`, icon: Clock },
  ]
  
  // Stock is stored in this browser so static deployments can use it without the optional API.
  const StockCard = () => (
    <Card className="min-w-0" data-testid="stock-data-card">
      <CardHeader className="gap-3 border-b py-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle>Stock data</CardTitle>
            <CardDescription className="mt-1">Upload real stock or use template</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-4">
        <div className="flex flex-col gap-3">
          <label className="flex items-center gap-2 rounded-lg border border-dashed p-3 text-sm hover:bg-muted">
            <Upload className="size-4" />
            <span className="flex-1 text-center">Upload stock CSV</span>
            <input
              type="file"
              accept=".csv"
              onChange={e => e.target.files?.[0] && handleStockUpload(e.target.files[0])}
              className="hidden"
            />
          </label>
          <button type="button" onClick={downloadTemplate} disabled={!data} className="flex items-center justify-center gap-2 rounded-lg border p-3 text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50">
            <FileText className="size-4" />
            Download template
          </button>
          {(savedStock || stockData?.active) && (
            <>
              <div className="text-xs text-muted-foreground">Active upload: {savedStock?.source_filename ?? stockData?.source_filename} ({savedStock?.row_count ?? stockData?.row_count} series)</div>
              <button onClick={handleClearStock} className="flex items-center justify-center gap-2 text-xs text-destructive hover:underline">
                <Trash2 className="size-3" />
                Clear uploaded stock
              </button>
            </>
          )}
          <div className="flex items-center justify-between rounded-lg bg-muted/50 p-3">
            <span className="text-xs">Use uploaded stock</span>
            <label className="relative inline-flex cursor-pointer items-center">
              <input type="checkbox" className="peer sr-only" checked={useUploadedStock} disabled={!savedStock && !stockData?.active} onChange={() => setUseUploadedStock(!useUploadedStock)} />
              <div className="peer h-6 w-11 rounded-full bg-gray-200 after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all peer-checked:bg-green-600 peer-checked:after:translate-x-full peer-checked:after:border-white after:border-gray-300 after:border after:content-['']"></div>
            </label>
          </div>
          {useUploadedStock && stockData?.active && (
            <div className="rounded-lg bg-muted/50 p-2 text-xs">
              <div className="font-medium">Active stock</div>
              <div className="text-muted-foreground">{stockNote}</div>
            </div>
          )}
          {stockUploadError && (
            <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive">
              <p>{stockUploadError.error}</p>
              {stockUploadError.errors?.map((item, index) => (
                <p key={`${item.line ?? "row"}-${index}`}>
                  {item.line ? `Line ${item.line}: ` : ""}{item.message}
                </p>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
  
  // What-if card for backend
  const WhatIfCard = () => backendOnline ? (
    <Card className="min-w-0">
      <CardHeader className="gap-3 border-b py-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle>What-if scenario</CardTitle>
            <CardDescription className="mt-1">Adjust demand uplift to see impact</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-4">
        <div className="flex flex-col gap-4">
          <div>
            <label htmlFor="whatif-uplift" className="text-xs font-medium">Demand uplift: {whatIfUplift}%</label>
            <input
              id="whatif-uplift"
              type="range"
              min={-50}
              max={200}
              step={5}
              value={whatIfUplift}
              onChange={e => setWhatIfUplift(Number(e.target.value))}
              className="mt-2 w-full"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor="whatif-start-day" className="text-xs font-medium">Start day: {whatIfStartDay}</label>
              <input
                id="whatif-start-day"
                type="range"
                min={1}
                max={30}
                value={whatIfStartDay}
                onChange={e => {
                  const day = Number(e.target.value)
                  setWhatIfStartDay(day)
                  if (whatIfEndDay < day) setWhatIfEndDay(day)
                }}
                className="mt-2 w-full"
              />
            </div>
            <div>
              <label htmlFor="whatif-end-day" className="text-xs font-medium">End day: {whatIfEndDay}</label>
              <input
                id="whatif-end-day"
                type="range"
                min={1}
                max={30}
                value={whatIfEndDay}
                onChange={e => {
                  const day = Number(e.target.value)
                  setWhatIfEndDay(day)
                  if (whatIfStartDay > day) setWhatIfStartDay(day)
                }}
                className="mt-2 w-full"
              />
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={handleWhatIf} disabled={whatIfLoading}>
            {whatIfLoading ? "Calculating..." : "Calculate scenario"}
          </Button>
          {whatIfError && <p role="alert" className="text-xs text-destructive">{whatIfError}</p>}
          {whatIfResult && (
            <div className="rounded-lg border bg-muted/50 p-3 text-xs">
              <div className="font-medium mb-2">Scenario impact</div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <div className="text-muted-foreground">Units before</div>
                  <div className="font-medium">{formatUnits(whatIfResult.baseline.summary.total_units)}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Units after</div>
                  <div className="font-medium">{formatUnits(whatIfResult.scenario.summary.total_units)}</div>
                </div>
                <div className="col-span-2">
                  <div className="text-muted-foreground">Top changes</div>
                  <ul className="mt-1 space-y-1">
                    {whatIfResult.delta.top_changes.slice(0, 5).map(change => (
                      <li key={change.series_id} className="flex justify-between gap-2">
                        <span>{change.series_id}: {formatUnits(change.qty_before)} → {formatUnits(change.qty_after)}</span>
                        <span className="shrink-0 text-muted-foreground">{change.priority_before} → {change.priority_after}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="mt-2 pt-2 border-t text-[10px] text-muted-foreground italic">{whatIfResult.disclaimer}</div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  ) : null
  
  return <div className="flex flex-col gap-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><h1>Restock list</h1><p className="mt-2 text-muted-foreground">Products whose forecast demand exceeds available stock</p></div><Button disabled={loading || !!failed || !rows.length} onClick={() => downloadRestockCsv(rows, options.horizon)}><Download data-icon="inline-start" />Download CSV</Button></div>
    <Alert role="note" className="p-4"><Info /><AlertTitle>{stockNote}</AlertTitle><AlertDescription>Adjust the assumptions below.</AlertDescription></Alert>
    <dl className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Restock summary" data-testid="restock-summary">{metrics.map(metric => <div key={metric.label} className="min-w-0 rounded-xl border bg-card p-4"><dt className="flex min-w-0 items-center gap-2 whitespace-normal break-normal text-xs text-muted-foreground"><metric.icon className="size-3.5 shrink-0" aria-hidden="true" /><span className="min-w-0">{metric.label}</span></dt><dd className="mt-3 text-2xl font-semibold tracking-tight">{loading ? <Skeleton className="h-8 w-20" /> : failed ? "—" : metric.value}</dd></div>)}</dl>
    <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="order-2 flex min-w-0 flex-col gap-6 xl:order-1">
        <Card className="min-w-0 gap-0 overflow-hidden py-0">
          <CardHeader className="gap-3 border-b py-5"><div className="flex min-w-0 flex-wrap items-start justify-between gap-2"><div className="min-w-0"><CardTitle>Recommended orders</CardTitle><CardDescription className="mt-1">{options.horizon}-day forecast · Jan 2018 · {filters.store === "all" ? "All stores" : `Store ${filters.store}`}</CardDescription></div><span className="text-xs text-muted-foreground">Select a product to see the calculation</span></div><RestockMobileSort sort={sort} onSort={changeSort} /></CardHeader>
          {failed ? <CardContent className="py-10"><Empty><EmptyHeader><EmptyTitle>Unable to load restock data</EmptyTitle><EmptyDescription>{typeof failed === "string" ? failed : computed.error ?? "Please retry loading the inventory assumptions."}</EmptyDescription></EmptyHeader><Button variant="outline" onClick={() => { void mutate(); void mutateUploadedRestock() }}>Retry</Button></Empty></CardContent>
            : loading ? <CardContent className="flex flex-col gap-4 py-6" role="status" aria-label="Loading restock list">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-10 w-full" />)}</CardContent>
            : !rows.length ? <Empty className="min-h-80"><EmptyHeader><EmptyTitle>Nothing to restock with these settings.</EmptyTitle><EmptyDescription>Try a different store, priority, or stock assumption.</EmptyDescription></EmptyHeader><Button variant="outline" onClick={reset}>Reset to defaults</Button></Empty>
            : <RestockTable rows={visibleRows} horizon={options.horizon} sort={sort} onSort={changeSort} onOpen={row => setSelectedId(row.series_id)} />}
          {!loading && !failed && <RestockPagination total={rows.length} page={currentPage} pageSize={pageSize} onPage={setPage} onPageSize={size => { setPageSize(size); setPage(1) }} />}
        </Card>
        <p className="text-xs leading-5 text-muted-foreground">Summary and CSV include all filtered products, not just this page. Orders include safety stock and round up to whole units. Forecasts are from Prophet (Jan 2018). Inventory assumptions use the 28-day trailing mean from the training data.</p>
      </div>
      <div className="order-1 min-w-0 xl:order-2"><RestockControls options={options} filters={filters} onOptions={changeOptions} onFilters={changeFilters} onReset={reset} /></div>
    </div>
    <div className={backendOnline ? "grid min-w-0 gap-6 xl:grid-cols-2" : "grid min-w-0 gap-6"}>
      <StockCard />
      <WhatIfCard />
    </div>
    {selected && <RestockSheet row={selected} input={effectiveInputs?.[selected.series_id]} options={options} onClose={() => setSelectedId(null)} />}
  </div>
}
