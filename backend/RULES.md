# DemandLens Backend Rules

- Backend is OPTIONAL. Static JSON in public/data/ remains the source of truth for all read endpoints. The dashboard must keep working with the backend off.

- Python only. No database server. Persist small state as JSON files under backend/.state/ (gitignored).

- Never change anything in pipeline/ or public/data/ from backend code. Read-only access to them.

- No data leakage: any model fit uses only rows with date <= train_end. Never use rows after train_end for fitting.

- Series ids look like S{store}_I{item}, store 1-5, item 1-50, validate with regex ^S[1-5]_I([1-9]|[1-4][0-9]|50)$.

- Windows + PowerShell: do not use && in commands, use separate lines or ;.

- JSON responses must match lib/types.ts shapes (SeriesData, RestockRow, ForecastPoint, PortfolioRow, EdaData). Do not change lib/types.ts unless a task says so, new fields must be optional.

- Strict JSON: never emit NaN/Infinity (use allow_nan=False or sanitize).

- Every endpoint has a pytest. Tests must not be loosened to pass.

- After each task: run `python -m pytest backend/tests -q` and report the summary, then STOP and wait.

- Config via env vars with defaults: DEMANDLENS_DATA_DIR (default public/data), DEMANDLENS_RAW_CSV (default pipeline/data/raw/train.csv), DEMANDLENS_CORS_ORIGINS (default http://localhost:3000,http://127.0.0.1:3000).
