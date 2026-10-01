## Optional backend
DemandLens includes an optional FastAPI backend for live refits and inventory scenarios.
The static dashboard continues to work when the backend is stopped.
See [backend/README.md](backend/README.md) for setup, configuration, endpoints, and tests.
Launch it from the repository root with `.\backend\run_dev.ps1`.

Restock CSV uploads and the stock template also work without the backend; uploaded stock is saved in the current browser.
Set `NEXT_PUBLIC_API_URL` when building a production frontend only if it should connect to a deployed backend.
