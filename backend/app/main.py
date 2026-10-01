"""FastAPI app with CORS and read-only endpoints for JSON artifacts."""
import asyncio
import logging
import time
import threading
from collections import deque
from http import HTTPStatus
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException, Request, status, Query, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field, model_validator

from .config import CORS_ORIGINS, STATE_DIR, RAW_CSV
from .store import store, ArtifactStore
from .schemas import (
    Manifest, SeriesData, PortfolioRow, EdaData, RestockInput, RestockRow,
    RestockResponse, ForecastRefitResponse, WhatIfResponse,
)
from .restock import (
    compute_restock, summarize_restock, filter_restock, load_restock_inputs
)
from .forecast import refit, _executor as forecast_executor
from .whatif import compute_whatif, DISCLAIMER
from .stock import (
    get_stock_state, clear_stock_state, process_stock_upload,
    get_stock_state_with_count, get_stock_source_info, get_template_csv
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DemandLens API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

_REFIT_LIMIT = 10
_REFIT_WINDOW_SECONDS = 60
_refit_requests: dict[str, deque[float]] = {}
_refit_requests_lock = threading.Lock()


def _check_refit_rate_limit(client_key: str, now: Optional[float] = None) -> bool:
    """Return True when the client has exceeded the rolling one-minute limit."""
    current_time = time.monotonic() if now is None else now
    with _refit_requests_lock:
        requests = _refit_requests.setdefault(client_key, deque())
        while requests and requests[0] <= current_time - _REFIT_WINDOW_SECONDS:
            requests.popleft()
        if len(requests) >= _REFIT_LIMIT:
            return True
        requests.append(current_time)
        return False


@app.middleware("http")
async def request_logging_and_refit_limit(request: Request, call_next):
    started = time.perf_counter()
    response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    try:
        if request.method == "POST" and request.url.path == "/api/forecast/refit":
            client_key = request.client.host if request.client else "unknown"
            if _check_refit_rate_limit(client_key):
                response = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Too Many Requests",
                        "detail": "Forecast refit limit exceeded (10 requests per minute).",
                    },
                    headers={"Retry-After": str(_REFIT_WINDOW_SECONDS)},
                )
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        response_status = response.status_code
        return response
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "%s %s %s %.2fms",
            request.method,
            request.url.path,
            response_status,
            elapsed_ms,
        )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    try:
        error = HTTPStatus(exc.status_code).phrase
    except ValueError:
        error = "HTTP error"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error, "detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"error": "Validation Error", "detail": exc.errors()}),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal Server Error", "detail": "An unexpected error occurred."},
    )


# CORS middleware (per RULES.md)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ORIGINS if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Pydantic model for POST /api/restock request body
class RestockRequest(BaseModel):
    """Request body for POST /api/restock"""
    horizon: Literal[14, 30] = Field(30, description="Forecast horizon: 14 or 30")
    service_level: Literal[0.9, 0.95, 0.99] = Field(
        0.95, description="Service level: 0.9, 0.95, or 0.99"
    )
    lead_time: int = Field(3, strict=True, ge=1, le=14, description="Lead time in days")
    stock_multiplier: float = Field(
        1.0, ge=0.5, le=2.0, allow_inf_nan=False, description="Stock multiplier"
    )
    store: Optional[int] = Field(None, strict=True, ge=1, le=5)
    priority: Optional[Literal["HIGH", "MEDIUM", "LOW"]] = None
    only_restock: bool = Field(False, description="Only include rows with restock_qty > 0")
    use_uploaded_stock: bool = Field(False, description="Use uploaded stock if available")

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_filter_names(cls, values):
        if isinstance(values, dict):
            values = values.copy()
            if "store" not in values and "store_filter" in values:
                values["store"] = values.pop("store_filter")
            if "priority" not in values and "priority_filter" in values:
                values["priority"] = values.pop("priority_filter")
        return values


# Pydantic model for POST /api/forecast/refit request body
class ForecastRefitRequest(BaseModel):
    """Request body for POST /api/forecast/refit"""
    series_id: str = Field(..., description="Series ID: S{store}_I{item}")
    train_end: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Training end date (ISO format)",
    )
    horizon: int = Field(30, strict=True, ge=1, le=60, description="Forecast horizon (1-60)")


# Pydantic models for POST /api/whatif
class WhatIfScenario(BaseModel):
    """What-if scenario parameters"""
    demand_uplift_pct: float = Field(
        0, ge=-50, le=200, allow_inf_nan=False,
        description="Demand uplift percentage: -50..200",
    )
    start_day: int = Field(1, strict=True, ge=1, le=30, description="Start day (1-30)")
    end_day: int = Field(30, strict=True, ge=1, le=30, description="End day (1-30)")

    @model_validator(mode="after")
    def validate_day_range(self):
        if self.start_day > self.end_day:
            raise ValueError("start_day must be less than or equal to end_day")
        return self


class WhatIfOptions(BaseModel):
    """What-if restock options"""
    horizon: Literal[14, 30] = Field(30, description="Forecast horizon: 14 or 30")
    service_level: Literal[0.9, 0.95, 0.99] = Field(
        0.95, description="Service level: 0.9, 0.95, or 0.99"
    )
    lead_time: int = Field(3, strict=True, ge=1, le=14, description="Lead time in days")
    stock_multiplier: float = Field(
        1.0, ge=0.5, le=2.0, allow_inf_nan=False, description="Stock multiplier"
    )
    store: Optional[int] = Field(None, strict=True, ge=1, le=5)
    priority: Optional[Literal["HIGH", "MEDIUM", "LOW"]] = None
    only_restock: bool = Field(False, description="Only include rows with restock_qty > 0")
    use_uploaded_stock: bool = Field(False, description="Use uploaded stock if available")

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_filter_names(cls, values):
        if isinstance(values, dict):
            values = values.copy()
            if "store" not in values and "store_filter" in values:
                values["store"] = values.pop("store_filter")
            if "priority" not in values and "priority_filter" in values:
                values["priority"] = values.pop("priority_filter")
        return values


class WhatIfRequest(BaseModel):
    """Request body for POST /api/whatif"""
    scenario: WhatIfScenario
    options: WhatIfOptions
    series_id: Optional[str] = Field(
        None,
        pattern=r"^S[1-5]_I([1-9]|[1-4][0-9]|50)$",
        description="Optional series_id filter",
    )


# Pydantic models for stock upload
class StockUploadResponse(BaseModel):
    """Response for stock upload"""
    accepted_rows: int
    missing_series_count: int
    uploaded_at: str


class StockStateResponse(BaseModel):
    """Response for GET /api/stock"""
    active: bool
    uploaded_at: Optional[str] = None
    source_filename: Optional[str] = None
    row_count: Optional[int] = None


# Startup event: validate all and log problems
@app.on_event("startup")
async def startup_event():
    logger.info("DemandLens backend starting...")
    problems = store.validate_all()
    if problems:
        logger.warning(f"Validation issues found: {len(problems)}")
        for p in problems[:5]:  # Log first 5 to avoid spam
            logger.warning(f"  - {p}")
        if len(problems) > 5:
            logger.warning(f"  ... and {len(problems) - 5} more")
    else:
        logger.info("All artifacts validated successfully")
    logger.info(f"Series count: {store.get_series_count()}")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    try:
        from prophet import Prophet
        prophet_available = True
    except ImportError:
        prophet_available = False
    
    return {
        "status": "ok",
        "series_count": store.get_series_count(),
        "data_dir": str(store.data_dir),
        "prophet_available": prophet_available,
        "version": "0.1.0"
    }


@app.get("/api/manifest", response_model=Manifest)
async def get_manifest():
    """Load manifest.json."""
    return store.load_manifest()


@app.get("/api/series/{series_id}", response_model=SeriesData)
async def get_series(series_id: str):
    """Load series/<id>.json. Validate format, 404 for missing, 422 for invalid."""
    if not store.validate_series_id(series_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid series_id format: {series_id}. Must match ^S[1-5]_I([1-9]|[1-4][0-9]|50)$"
        )
    
    # Check if series exists (file not found -> 404)
    if store.is_series_missing(series_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Series not found: {series_id}"
        )
    
    try:
        return store.load_series(series_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load series: {e}"
        )


@app.get("/api/portfolio", response_model=list[PortfolioRow])
async def get_portfolio():
    """Load portfolio.json."""
    return store.load_portfolio()


@app.get("/api/eda", response_model=EdaData)
async def get_eda():
    """Load eda.json."""
    return store.load_eda()


@app.get("/api/restock-inputs", response_model=dict[str, RestockInput])
async def get_restock_inputs():
    """Load restock_inputs.json."""
    return store.load_restock_inputs()


@app.get("/api/stock", response_model=StockStateResponse)
async def get_stock():
    """Get current stock state."""
    state = get_stock_state()
    if not state:
        return {"active": False}
    
    return {
        "active": True,
        "uploaded_at": state.uploaded_at,
        "source_filename": state.source_filename,
        "row_count": state.row_count
    }


@app.post("/api/stock/upload", response_model=StockUploadResponse)
async def post_stock_upload(file: UploadFile = File(...)):
    """Upload stock CSV."""
    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid file type. Only CSV files are accepted.",
        )

    accepted_content_types = {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
    }
    if file.content_type not in accepted_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Invalid content type. Upload a CSV file with a CSV media type.",
        )

    # Validate file size (max 1 MB)
    file_size = 0
    csv_bytes = bytearray()
    
    # Read file content
    while True:
        chunk = await file.read(8192)
        if not chunk:
            break
        file_size += len(chunk)
        if file_size > 1024 * 1024:  # 1 MB
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large. Maximum size is 1 MB."
            )
        csv_bytes.extend(chunk)

    if not csv_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV file is empty.",
        )

    try:
        csv_content = csv_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV must be UTF-8 encoded.",
        ) from exc

    # Process upload
    try:
        state = process_stock_upload(csv_content, filename)
    except ValueError as e:
        # Validation errors from parse_stock_csv
        errors = e.args[0]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"errors": errors}
        )
    
    _, accepted_rows, missing_series_count = get_stock_state_with_count()
    
    return StockUploadResponse(
        accepted_rows=accepted_rows,
        missing_series_count=missing_series_count,
        uploaded_at=state.uploaded_at
    )


@app.delete("/api/stock")
async def delete_stock():
    """Clear stock state."""
    clear_stock_state()
    return {"message": "Stock state cleared"}


@app.get("/api/stock/template")
async def get_stock_template():
    """Get CSV template with simulated stock values."""
    template_csv = get_template_csv()
    return PlainTextResponse(content=template_csv, media_type="text/csv")


@app.post("/api/restock", response_model=RestockResponse)
async def post_restock(request: RestockRequest):
    """Compute restock recommendations."""
    # Validate inputs (Pydantic handles type checking)
    try:
        # Load inputs
        inputs = load_restock_inputs()
        
        # If use_uploaded_stock is enabled, override with uploaded stock
        if request.use_uploaded_stock:
            state = get_stock_state()
            if state:
                for sid, stock in state.rows.items():
                    if sid in inputs:
                        inputs[sid] = inputs[sid].model_copy(
                            update={"current_stock": stock}
                        )
        
        # Compute restock
        rows = compute_restock(inputs, request.horizon, request.service_level, 
                               request.lead_time, request.stock_multiplier)
        
        # Apply filters
        rows = filter_restock(rows, request.store, request.priority, request.only_restock)
        
        # Compute summary
        summary = summarize_restock(rows)
        
        # Determine stock source info
        stock_source, _ = get_stock_source_info(
            request.use_uploaded_stock,
            [row.series_id for row in rows],
        )
        
        return {
            "rows": rows,
            "summary": summary,
            "stock_source": stock_source
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute restock: {e}"
        )


@app.post("/api/forecast/refit", response_model=ForecastRefitResponse)
async def post_forecast_refit(request: ForecastRefitRequest):
    """Refit Prophet for a single series and forecast."""
    # Validate series_id format
    if not store.validate_series_id(request.series_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid series_id: {request.series_id}. Must match ^S[1-5]_I([1-9]|[1-4][0-9]|50)$"
        )
    
    # Validate train_end calendar date and permitted range.
    from datetime import date
    try:
        train_end = date.fromisoformat(request.train_end)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid train_end format: {request.train_end}. Must be ISO format (YYYY-MM-DD)."
        )
    
    # Validate date range (2014-01-01 to 2017-12-31)
    if train_end < date(2014, 1, 1) or train_end > date(2017, 12, 31):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"train_end must be between 2014-01-01 and 2017-12-31. Got: {request.train_end}"
        )
    
    try:
        loop = asyncio.get_running_loop()
        fit_future = loop.run_in_executor(
            forecast_executor,
            refit,
            request.series_id,
            train_end,
            request.horizon,
        )
        return await asyncio.wait_for(fit_future, timeout=90)
    
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except asyncio.TimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Forecast refit exceeded the 90 second timeout.",
        ) from e
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refit forecast: {e}"
        )


@app.post("/api/whatif", response_model=WhatIfResponse)
async def post_whatif(request: WhatIfRequest):
    """Scenario analysis on top of existing forecasts."""
    scenario = request.scenario
    options = request.options
    series_id = request.series_id
    
    # Validate scenario parameters
    if scenario.demand_uplift_pct < -50 or scenario.demand_uplift_pct > 200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid demand_uplift_pct: {scenario.demand_uplift_pct}. Must be -50..200."
        )
    
    if scenario.start_day < 1 or scenario.start_day > 30:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid start_day: {scenario.start_day}. Must be 1..30."
        )
    
    if scenario.end_day < 1 or scenario.end_day > 30:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid end_day: {scenario.end_day}. Must be 1..30."
        )
    
    if scenario.start_day > scenario.end_day:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"start_day ({scenario.start_day}) > end_day ({scenario.end_day})"
        )
    
    # Validate options
    if options.horizon not in (14, 30):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid horizon: {options.horizon}. Must be 14 or 30."
        )
    
    if options.service_level not in (0.9, 0.95, 0.99):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid service_level: {options.service_level}. Must be 0.9, 0.95, or 0.99."
        )
    
    # Validate series_id if provided
    if series_id and not store.validate_series_id(series_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid series_id: {series_id}. Must match ^S[1-5]_I([1-9]|[1-4][0-9]|50)$"
        )
    
    try:
        # Determine if using uploaded stock
        use_uploaded = options.use_uploaded_stock and get_stock_state() is not None
        
        result = compute_whatif(
            scenario={
                "demand_uplift_pct": scenario.demand_uplift_pct,
                "start_day": scenario.start_day,
                "end_day": scenario.end_day
            },
            options={
                "horizon": options.horizon,
                "service_level": options.service_level,
                "lead_time": options.lead_time,
                "stock_multiplier": options.stock_multiplier,
                "store": options.store,
                "priority": options.priority,
                "only_restock": options.only_restock
            },
            series_id_filter=series_id,
            use_uploaded_stock=use_uploaded
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute what-if scenario: {e}"
        )
