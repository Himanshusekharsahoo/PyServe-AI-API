from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.router import api_router
from app.core.config import API_PREFIX, APP_NAME, APP_VERSION, IS_DEBUG
from app.core.event_handlers import start_app_handler, stop_app_handler
from app.core.logging import logger

def create_app() -> FastAPI:
    """
    Initialize FastAPI application with routes, middleware,
    event handlers, and configuration settings.
    """
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        debug=IS_DEBUG,
        description="PyServe AI API — Lightweight ML Model Serving Framework",
    )
    # Enable CORS (Optional but useful for frontend/clients)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Routers
    app.include_router(api_router, prefix=API_PREFIX)
    # Lifecycle events
    app.add_event_handler("startup", start_app_handler(app))
    app.add_event_handler("shutdown", stop_app_handler(app))
    logger.info(f"{APP_NAME} v{APP_VERSION} initialized successfully.")
    return app
app = create_app()
