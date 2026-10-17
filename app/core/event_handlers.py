from typing import Callable

from fastapi import FastAPI

from app.core.config import DEFAULT_MODEL_PATH, validate_config
from app.core.logging import logger
from app.services.model_service import ModelLoadError, get_model_service


def _startup_model(app: FastAPI) -> None:
    service = get_model_service()
    try:
        service.load(DEFAULT_MODEL_PATH)
        app.state.model_service = service
        logger.info("Sentiment model service initialized successfully.")
    except ModelLoadError as exc:
        app.state.model_service = service
        logger.warning(
            f"Sentiment model could not be loaded during startup: {exc}. "
            "Inference endpoints will report 503 until a valid model artifact is "
            "deployed."
        )


def _shutdown_model(app: FastAPI) -> None:
    service = getattr(app.state, "model_service", None)
    if service is not None:
        service.unload()
    app.state.model_service = None
    logger.info("Application model resources released.")


def start_app_handler(app: FastAPI) -> Callable:
    def startup() -> None:
        logger.info("Running app start handler.")
        validate_config()
        _startup_model(app)

    return startup


def stop_app_handler(app: FastAPI) -> Callable:
    def shutdown() -> None:
        logger.info("Running app shutdown handler.")
        _shutdown_model(app)

    return shutdown
