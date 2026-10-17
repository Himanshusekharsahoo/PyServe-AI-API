from pydantic import BaseModel, Field


class HeartbeatResult(BaseModel):
    """
    Schema for health check heartbeat responses.
    """

    is_alive: bool = Field(..., description="Service liveness status indicator.")


class ReadinessResult(BaseModel):
    """Whether this process can currently serve model inference."""

    is_ready: bool = Field(..., description="Model inference readiness indicator.")


class MetricsResult(BaseModel):
    """Operational service metrics."""

    worker_pid: int = Field(
        ..., description="Process ID of the worker servicing the request."
    )
    uptime_seconds: float = Field(..., description="Process uptime in elapsed seconds.")
    total_requests: int = Field(..., description="Total HTTP requests processed.")
    total_predictions: int = Field(
        ..., description="Total sentiment prediction requests."
    )
    total_errors: int = Field(
        ..., description="Total HTTP 4xx and 5xx error responses."
    )
    model_loaded: bool = Field(
        ..., description="Whether the sentiment model is loaded."
    )


# Backward compatibility alias for the legacy typo
HearbeatResult = HeartbeatResult
