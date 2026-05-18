"""FastAPI application factory for the FitGraph inference service."""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from fitgraph.api.routes import router
from fitgraph.api.serving import get_model_service, latest_model_dir

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory ring buffer for per-request latency (P99 tracking)
# ---------------------------------------------------------------------------

_LATENCY_WINDOW = 500  # keep the last 500 request times
_latency_ring: deque[float] = deque(maxlen=_LATENCY_WINDOW)


def _record_latency(ms: float) -> None:
    _latency_ring.append(ms)


def get_p99_latency_ms() -> float | None:
    """Return the P99 response latency over the last request window, in ms."""
    if not _latency_ring:
        return None
    arr = np.array(list(_latency_ring), dtype=np.float64)
    return float(np.percentile(arr, 99))


# ---------------------------------------------------------------------------
# Lifespan: load model if a checkpoint exists at startup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    svc = get_model_service()
    model_dir = latest_model_dir()
    if model_dir is not None:
        try:
            svc.load(model_dir)
            logger.info("Loaded model %s at startup", svc.current_version)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load model at startup: %s", exc)
    else:
        logger.info(
            "No model checkpoint found at startup — endpoints requiring the model "
            "will return 503 until a checkpoint is available."
        )
    yield
    # Shutdown — nothing to clean up for now


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FitGraph FastAPI application."""
    app = FastAPI(
        title="FitGraph",
        description="Outfit compatibility GNN inference service",
        version="0.1.0",
        lifespan=_lifespan,
    )

    # Permissive CORS for the local Next.js frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Latency middleware — lightweight, in-memory only
    @app.middleware("http")
    async def _latency_middleware(request: Request, call_next: object) -> Response:
        t0 = time.perf_counter()
        response: Response = await call_next(request)  # type: ignore[arg-type,operator]
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        _record_latency(elapsed_ms)
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response

    app.include_router(router)
    return app


# Allow running with ``uvicorn fitgraph.api.main:app``
app = create_app()
