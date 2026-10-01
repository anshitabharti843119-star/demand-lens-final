# DemandLens Optional FastAPI Backend

The backend is optional. The dashboard's static JSON assets in `public/data/` remain the source of truth for read-only dashboard data, so the frontend continues to work in Static mode when this service is stopped.

## Setup

From the repository root, create and activate a virtual environment, then install the pinned backend dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
```

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt` and run Uvicorn through that interpreter.

## Run

From the repository root:

```powershell
.\backend\run_dev.ps1
```

The script runs `python -m uvicorn backend.app.main:app --reload --port 8000`. The API docs are at `http://127.0.0.1:8000/docs`.

## Configuration

Set optional environment variables in PowerShell before starting the server. Relative paths are resolved from the repository root.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEMANDLENS_DATA_DIR` | `public/data` | Static JSON artifact directory |
| `DEMANDLENS_RAW_CSV` | `pipeline/data/raw/train.csv` | Local training CSV used for live Prophet refits |
| `DEMANDLENS_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated browser origins allowed by CORS |

Example:

```powershell
$env:DEMANDLENS_DATA_DIR = "public/data"
$env:DEMANDLENS_RAW_CSV = "pipeline/data/raw/train.csv"
$env:DEMANDLENS_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
.\backend\run_dev.ps1
```

## Endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /api/health` | Service status, artifact count, and Prophet availability |
| `GET /api/manifest` | Dataset manifest |
| `GET /api/series/{series_id}` | One validated series, e.g. `S1_I1` |
| `GET /api/portfolio` | Portfolio metrics |
| `GET /api/eda` | Exploratory data analysis |
| `GET /api/restock-inputs` | Static stock assumptions and forecasts |
| `POST /api/restock` | Compute restock recommendations |
| `POST /api/forecast/refit` | Live Prophet fit for one series (10 requests/minute/client) |
| `POST /api/whatif` | Demand uplift scenario |
| `GET /api/stock` | Current uploaded-stock status |
| `POST /api/stock/upload` | Upload a UTF-8 CSV (`text/csv`, max 1 MiB) |
| `DELETE /api/stock` | Clear uploaded stock |
| `GET /api/stock/template` | Download a sample stock CSV |

PowerShell examples:

```powershell
$base = "http://127.0.0.1:8000"
foreach ($path in @("/api/health", "/api/manifest", "/api/series/S1_I1",
    "/api/portfolio", "/api/eda", "/api/restock-inputs", "/api/stock")) {
  Invoke-RestMethod "$base$path"
}
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/restock `
  -ContentType "application/json" -Body "{}"
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/forecast/refit `
  -ContentType "application/json" `
  -Body '{"series_id":"S1_I1","train_end":"2017-11-30","horizon":30}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/stock/upload `
  -Form @{ file = (Get-Item .\stock.csv) }
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/whatif `
  -ContentType "application/json" `
  -Body '{"scenario":{"demand_uplift_pct":30,"start_day":5,"end_day":15},"options":{}}'
Invoke-RestMethod -Method Delete http://127.0.0.1:8000/api/stock
```

For the CSV template, download it with `curl.exe -o stock_template.csv "$base/api/stock/template"`. The multipart `-Form` upload example requires PowerShell 7; the `curl.exe` example below also works on Windows PowerShell 5.1.

Equivalent `curl.exe` examples:

```powershell
curl.exe http://127.0.0.1:8000/api/health
curl.exe http://127.0.0.1:8000/api/manifest
curl.exe http://127.0.0.1:8000/api/series/S1_I1
curl.exe http://127.0.0.1:8000/api/portfolio
curl.exe http://127.0.0.1:8000/api/eda
curl.exe http://127.0.0.1:8000/api/restock-inputs
curl.exe http://127.0.0.1:8000/api/stock
curl.exe -o stock_template.csv http://127.0.0.1:8000/api/stock/template
curl.exe -X POST http://127.0.0.1:8000/api/restock -H "Content-Type: application/json" -d "{}"
curl.exe -X POST http://127.0.0.1:8000/api/forecast/refit -H "Content-Type: application/json" -d '{"series_id":"S1_I1","train_end":"2017-11-30","horizon":30}'
curl.exe -X POST http://127.0.0.1:8000/api/stock/upload -F "file=@stock.csv;type=text/csv"
curl.exe -X POST http://127.0.0.1:8000/api/whatif -H "Content-Type: application/json" -d '{"scenario":{"demand_uplift_pct":30,"start_day":5,"end_day":15},"options":{}}'
curl.exe -X DELETE http://127.0.0.1:8000/api/stock
```

## Tests

From the repository root:

```powershell
python -m pytest backend/tests -q
npm test
```

## Static mode and known limits

- Backend read endpoints serve the same static JSON artifacts used by the frontend. The backend is an optional enhancement; when it is off, the dashboard should remain usable in Static mode.
- Live refit requires Prophet, CmdStan, and the raw `train.csv` at `DEMANDLENS_RAW_CSV`. The verified S1_I1, 30-day fit in this environment took 2.936 seconds; a cold CmdStan initialization or slower demo machine can take longer. Repeat identical requests use the local fit cache.
- Prophet may need to compile or initialize its CmdStan model the first time. Pre-warm after starting the API by calling `POST /api/forecast/refit` for `S1_I1` with `train_end` `2017-11-30` and horizon `30`; verify the JSON reports `cached: true` on a second call.
- On Windows, CmdStan discovery or execution can fail if its installation path is missing, blocked by security software, or inaccessible to the selected Python environment. Before the demo, verify `python -c "import cmdstanpy; print(cmdstanpy.cmdstan_path())"` and run the pre-warm refit from that same environment.
- Windows security software or the firewall may prompt on the first Uvicorn launch. Allow Python on the local/private network only if the demo needs another device to connect; localhost use does not require opening a public firewall port.
- Uploaded stock is a single-process in-memory/JSON state under `backend/.state/`; it is not a database, is not intended for concurrent multi-worker deployments, and should be cleared after demos if it contains real inventory data.
- The API has no authentication. Keep it bound to localhost or a trusted private demo network; do not expose it publicly.
- Live refits are limited to 10 requests per client per rolling minute in a single process. Rate limits and stock state are not shared across multiple workers.
