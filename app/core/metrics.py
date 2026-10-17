import os
import time
from typing import Any, Dict

_start_time = time.time()
_total_requests = 0
_total_predictions = 0
_total_errors = 0


def record_request() -> None:
    global _total_requests
    _total_requests += 1


def record_prediction() -> None:
    global _total_predictions
    _total_predictions += 1


def record_error() -> None:
    global _total_errors
    _total_errors += 1


def get_metrics_snapshot() -> Dict[str, Any]:
    """
    Returns process-local telemetry metrics for the current worker process.
    In multi-worker ASGI environments (e.g. Uvicorn --workers 2), counters are
    maintained per-worker and should be aggregated using worker_pid.
    """
    return {
        "worker_pid": os.getpid(),
        "uptime_seconds": round(time.time() - _start_time, 2),
        "total_requests": _total_requests,
        "total_predictions": _total_predictions,
        "total_errors": _total_errors,
    }
