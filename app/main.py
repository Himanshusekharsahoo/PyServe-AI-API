from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.router import api_router
from app.core import config
from app.core.config import (
    ALLOWED_ORIGINS,
    API_PREFIX,
    APP_NAME,
    APP_VERSION,
    IS_DEBUG,
)
from app.core.event_handlers import start_app_handler, stop_app_handler
from app.core.logging import logger
from app.core.middleware import (
    CorrelationIdMiddleware,
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)


def create_app() -> FastAPI:
    """
    Initialize FastAPI application with routes, middleware,
    event handlers, and configuration settings.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        start_app_handler(app)()
        yield
        stop_app_handler(app)()

    # In production, disable interactive documentation and OpenAPI schema by default
    docs_url = None if config.ENVIRONMENT == "production" else "/docs"
    redoc_url = None if config.ENVIRONMENT == "production" else "/redoc"
    openapi_url = None if config.ENVIRONMENT == "production" else "/openapi.json"

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        debug=IS_DEBUG,
        description="PyServe AI API — Lightweight ML Model Serving Framework",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # Operational middlewares (Starlette executes middlewares in reverse addition order)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # Enable CORS with explicit origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(api_router, prefix=API_PREFIX)
    logger.info(f"{APP_NAME} v{APP_VERSION} initialized successfully.")
    return app


app = create_app()

# Backward compatibility alias for upstream callers
get_app = create_app
