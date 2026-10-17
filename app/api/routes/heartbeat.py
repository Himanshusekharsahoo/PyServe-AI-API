from fastapi import APIRouter, Response, status

from app.core.metrics import get_metrics_snapshot
from app.models.heartbeat import HeartbeatResult, MetricsResult, ReadinessResult
from app.services.model_service import get_model_service

router = APIRouter()


@router.get(
    "/heartbeat",
    response_model=HeartbeatResult,
    name="heartbeat",
    summary="Health check / liveness probe",
    description="Returns the alive status of the PyServe AI API service.",
)
def get_heartbeat() -> HeartbeatResult:
    """Check service health and liveness."""
    return HeartbeatResult(is_alive=True)


# Backwards compatibility alias
get_hearbeat = get_heartbeat


@router.get("/ready", response_model=ReadinessResult, name="readiness")
def get_readiness(response: Response) -> ReadinessResult:
    """Report whether the model is available to serve inference."""
    is_ready = get_model_service().is_loaded
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResult(is_ready=is_ready)


@router.get("/metrics", response_model=MetricsResult, name="metrics")
def get_metrics() -> MetricsResult:
    """Operational service metrics."""
    snapshot = get_metrics_snapshot()
    return MetricsResult(
        worker_pid=snapshot["worker_pid"],
        uptime_seconds=snapshot["uptime_seconds"],
        total_requests=snapshot["total_requests"],
        total_predictions=snapshot["total_predictions"],
        total_errors=snapshot["total_errors"],
        model_loaded=get_model_service().is_loaded,
    )
