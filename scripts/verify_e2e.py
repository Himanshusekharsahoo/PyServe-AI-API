"""
Comprehensive End-to-End Live Verification Script for PyServe AI API.
Spins up a live Uvicorn instance on 127.0.0.1:8000 and performs real HTTP requests.
Includes bounded timeouts, immediate output flushing, and safe cleanup.
"""

import http.client
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.request

API_KEY = "production-secret-token-exceeding-32-chars-strictly-secure"
PORT = 8000
BASE_URL = f"http://127.0.0.1:{PORT}"
HTTP_TIMEOUT = 5.0


def log(msg: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def cleanup_process(proc: subprocess.Popen) -> None:
    """Safely terminate a process and its child processes on Windows or POSIX."""
    if proc.poll() is not None:
        return
    log(f"Terminating server process PID {proc.pid}...")
    try:
        # On Windows, taskkill /T /F ensures all children are terminated
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        else:
            proc.terminate()
            proc.wait(timeout=3)
    except Exception as e:
        log(f"Warning during process cleanup: {e}")
        try:
            proc.kill()
        except Exception:
            pass


def make_request(
    method: str,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    data: Any = None,
) -> Tuple[int, Dict[str, str], Any]:
    url = f"{BASE_URL}{path}"
    req_headers = headers.copy() if headers else {}
    body = None
    if data is not None:
        if isinstance(data, dict):
            body = json.dumps(data).encode("utf-8")
            if "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "application/json"
        elif isinstance(data, str):
            body = data.encode("utf-8")
        elif isinstance(data, bytes):
            body = data

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            status = resp.status
            resp_headers = dict(resp.headers)
            resp_body = resp.read().decode("utf-8")
            try:
                parsed = json.loads(resp_body)
            except Exception:
                parsed = resp_body
            return status, resp_headers, parsed
    except urllib.error.HTTPError as err:
        resp_headers = dict(err.headers)
        resp_body = err.read().decode("utf-8")
        try:
            parsed = json.loads(resp_body)
        except Exception:
            parsed = resp_body
        return err.code, resp_headers, parsed
    except Exception as exc:
        return 0, {}, str(exc)


def make_chunked_request(
    path: str,
    chunks: List[bytes],
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Dict[str, str], Any]:
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=HTTP_TIMEOUT)
    req_headers = headers.copy() if headers else {}
    try:
        conn.request(
            "POST", path, body=chunks, headers=req_headers, encode_chunked=True
        )
        resp = conn.getresponse()
        status = resp.status
        resp_headers = dict(resp.headers)
        body = resp.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
        return status, resp_headers, parsed
    except Exception as e:
        try:
            resp = conn.getresponse()
            status = resp.status
            resp_headers = dict(resp.headers)
            body = resp.read().decode("utf-8")
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = body
            return status, resp_headers, parsed
        except Exception:
            return 0, {}, str(e)
    finally:
        conn.close()


def run_checks() -> bool:
    results: List[Tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        results.append((name, condition, detail))
        status_str = "PASS" if condition else "FAIL"
        log(f"[{status_str}] {name} {detail}")

    log("--- Step 1: Health, Readiness & Metrics Endpoints ---")
    s, h, b = make_request("GET", "/api/health/heartbeat")
    check(
        "Liveness probe returns 200",
        s == 200 and isinstance(b, dict) and b.get("is_alive") is True,
        f"status={s}, body={b}",
    )
    check(
        "Liveness probe returns X-Request-ID",
        "x-request-id" in [k.lower() for k in h.keys()],
        f"headers={list(h.keys())}",
    )
    check(
        "Security header X-Content-Type-Options: nosniff present",
        (h.get("x-content-type-options") or h.get("X-Content-Type-Options"))
        == "nosniff",
        f"val={h.get('x-content-type-options') or h.get('X-Content-Type-Options')}",
    )
    check(
        "Security header X-Frame-Options: DENY present",
        (h.get("x-frame-options") or h.get("X-Frame-Options")) == "DENY",
        f"val={h.get('x-frame-options') or h.get('X-Frame-Options')}",
    )
    check(
        "Security header Referrer-Policy: no-referrer present",
        (h.get("referrer-policy") or h.get("Referrer-Policy")) == "no-referrer",
        f"val={h.get('referrer-policy') or h.get('Referrer-Policy')}",
    )
    check(
        "Security header Content-Security-Policy present",
        "default-src 'none'"
        in (h.get("content-security-policy") or h.get("Content-Security-Policy") or ""),
        f"val={h.get('content-security-policy') or h.get('Content-Security-Policy')}",
    )
    check(
        "Security header Permissions-Policy present",
        "camera=()"
        in (h.get("permissions-policy") or h.get("Permissions-Policy") or ""),
        f"val={h.get('permissions-policy') or h.get('Permissions-Policy')}",
    )

    s_bad_corr, h_bad_corr, _ = make_request(
        "GET",
        "/api/health/heartbeat",
        headers={"X-Request-ID": "<script>alert(1)</script>"},
    )
    returned_corr = h_bad_corr.get("x-request-id") or h_bad_corr.get("X-Request-ID", "")
    check(
        "Malformed X-Request-ID is sanitized to UUID4 and not reflected",
        s_bad_corr == 200
        and returned_corr != "<script>alert(1)</script>"
        and len(returned_corr) == 36,
        f"returned_id={returned_corr}",
    )

    s, h, b = make_request("GET", "/api/health/ready")
    check(
        "Readiness probe returns 200 when model loaded",
        s == 200 and isinstance(b, dict) and b.get("is_ready") is True,
        f"status={s}, body={b}",
    )
    check(
        "Readiness probe returns X-Request-ID",
        "x-request-id" in [k.lower() for k in h.keys()],
    )

    s, h, b = make_request("GET", "/api/health/metrics")
    check("Metrics endpoint returns 200", s == 200, f"status={s}")
    required_metric_fields = (
        "worker_pid",
        "uptime_seconds",
        "total_requests",
        "total_predictions",
        "total_errors",
        "model_loaded",
    )
    check(
        "Metrics returns documented schema including process-local worker_pid",
        isinstance(b, dict)
        and all(k in b for k in required_metric_fields)
        and isinstance(b.get("worker_pid"), int)
        and b.get("worker_pid", 0) > 0,
        f"keys={list(b.keys()) if isinstance(b, dict) else b}",
    )

    log("--- Step 2: Authentication Verification ---")
    s, h, b = make_request("POST", "/api/model/predict", data={"text": "Hello"})
    check("Missing API key returns HTTP 401", s == 401, f"status={s}")
    check(
        "401 response includes X-Request-ID",
        "x-request-id" in [k.lower() for k in h.keys()],
    )

    s, h, b = make_request(
        "POST",
        "/api/model/predict",
        headers={"token": "incorrect-token-value-12345"},
        data={"text": "Hello"},
    )
    check("Invalid API key returns HTTP 401", s == 401, f"status={s}")

    log("--- Step 3: Sentiment Prediction (Positive & Negative) ---")
    auth_header = {"token": API_KEY}
    s, h, b = make_request(
        "POST",
        "/api/model/predict",
        headers=auth_header,
        data={"text": "The platform is incredibly fast, dependable, and intuitive."},
    )
    check("Positive inference returns 200", s == 200, f"status={s}")
    check(
        "Positive inference classified as 'positive'",
        isinstance(b, dict) and b.get("sentiment") == "positive",
        f"sentiment={b.get('sentiment') if isinstance(b, dict) else b}",
    )
    check(
        "Positive inference confidence > 0.5",
        isinstance(b, dict) and float(b.get("confidence", 0)) > 0.5,
        f"confidence={b.get('confidence') if isinstance(b, dict) else b}",
    )
    check(
        "Positive inference response includes X-Request-ID",
        "x-request-id" in [k.lower() for k in h.keys()],
    )

    s, h, b = make_request(
        "POST",
        "/api/model/predict",
        headers=auth_header,
        data={"text": "This product was terrible, completely broken, and useless."},
    )
    check("Negative inference returns 200", s == 200, f"status={s}")
    check(
        "Negative inference classified as 'negative'",
        isinstance(b, dict) and b.get("sentiment") == "negative",
        f"sentiment={b.get('sentiment') if isinstance(b, dict) else b}",
    )
    check(
        "Negative inference confidence > 0.5",
        isinstance(b, dict) and float(b.get("confidence", 0)) > 0.5,
        f"confidence={b.get('confidence') if isinstance(b, dict) else b}",
    )

    log("--- Step 4: Payload Validation (Empty, Whitespace, Excessive Length) ---")
    s, h, b = make_request(
        "POST", "/api/model/predict", headers=auth_header, data={"text": ""}
    )
    check("Empty string payload rejected with 422", s == 422, f"status={s}")
    check(
        "422 response includes X-Request-ID",
        "x-request-id" in [k.lower() for k in h.keys()],
    )

    s, h, b = make_request(
        "POST", "/api/model/predict", headers=auth_header, data={"text": "      "}
    )
    check("Whitespace-only payload rejected with 422", s == 422, f"status={s}")

    s, h, b = make_request(
        "POST", "/api/model/predict", headers=auth_header, data={"text": "a" * 5001}
    )
    check(
        "Excessively long text (>5000 chars) rejected with 422", s == 422, f"status={s}"
    )

    log("--- Step 5: Request Size Limiting (HTTP 413) ---")
    oversized_data = b"x" * 70000
    oversized_headers = dict(auth_header)
    oversized_headers["Content-Type"] = "application/octet-stream"
    s, h, b = make_request(
        "POST", "/api/model/predict", headers=oversized_headers, data=oversized_data
    )
    check(
        "Oversized payload with Content-Length (>64KB) returns HTTP 413",
        s == 413,
        f"status={s}",
    )
    check(
        "413 response includes X-Request-ID",
        "x-request-id" in [k.lower() for k in h.keys()],
    )

    s_chunk, h_chunk, b_chunk = make_chunked_request(
        "/api/model/predict",
        chunks=[b"x" * 35000, b"x" * 35000],
        headers=dict(auth_header, **{"Content-Type": "application/octet-stream"}),
    )
    check(
        "Chunked streaming payload exceeding max bytes returns HTTP 413",
        s_chunk == 413,
        f"status={s_chunk}, body={b_chunk}",
    )
    check(
        "Chunked 413 response includes X-Request-ID",
        "x-request-id" in [k.lower() for k in h_chunk.keys()],
    )

    log("--- Step 6: CORS Origins Verification ---")
    preflight_headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
    }
    s, h, b = make_request("OPTIONS", "/api/model/predict", headers=preflight_headers)
    allow_origin = h.get("Access-Control-Allow-Origin") or h.get(
        "access-control-allow-origin"
    )
    allow_creds = h.get("Access-Control-Allow-Credentials") or h.get(
        "access-control-allow-credentials"
    )
    check(
        "Allowed CORS origin permitted in preflight",
        s == 200 and allow_origin == "http://localhost:3000",
        f"status={s}, origin={allow_origin}",
    )
    check(
        "CORS credentials allowed", allow_creds == "true", f"credentials={allow_creds}"
    )

    untrusted_headers = {
        "Origin": "http://untrusted-third-party.com",
        "Access-Control-Request-Method": "POST",
    }
    s, h, b = make_request("OPTIONS", "/api/model/predict", headers=untrusted_headers)
    bad_origin = h.get("Access-Control-Allow-Origin") or h.get(
        "access-control-allow-origin"
    )
    check(
        "Untrusted CORS origin rejected in preflight",
        bad_origin is None,
        f"origin={bad_origin}",
    )

    log("--- Step 6.5: Production API Documentation Disabled (HTTP 404) ---")
    s_docs, _, _ = make_request("GET", "/docs")
    check(
        "Interactive Swagger UI (/docs) returns HTTP 404 in production",
        s_docs == 404,
        f"status={s_docs}",
    )
    s_redoc, _, _ = make_request("GET", "/redoc")
    check(
        "ReDoc UI (/redoc) returns HTTP 404 in production",
        s_redoc == 404,
        f"status={s_redoc}",
    )
    s_openapi, _, _ = make_request("GET", "/openapi.json")
    check(
        "OpenAPI schema (/openapi.json) returns HTTP 404 in production",
        s_openapi == 404,
        f"status={s_openapi}",
    )

    log("--- Step 7: Rate Limiting Verification (HTTP 429 & Retry-After) ---")
    hit_429 = False
    retry_after_val = None
    rate_x_req_id = None
    req_count = 0
    for req_idx in range(70):
        req_count += 1
        s, h, b = make_request("GET", "/api/health/heartbeat")
        if s == 429:
            hit_429 = True
            retry_after_val = h.get("Retry-After") or h.get("retry-after")
            rate_x_req_id = h.get("X-Request-ID") or h.get("x-request-id")
            break

    check(
        "Rate limit triggers HTTP 429 under excessive requests",
        hit_429,
        f"triggered after {req_count} requests",
    )
    check(
        "429 response includes valid Retry-After header",
        retry_after_val == "60",
        f"Retry-After={retry_after_val}",
    )
    check(
        "429 response includes X-Request-ID header",
        rate_x_req_id is not None,
        f"X-Request-ID={rate_x_req_id}",
    )

    failures = [r for r in results if not r[1]]
    log("==========================================")
    passed_count = len(results) - len(failures)
    log(f"E2E Normal Server Results: {passed_count}/{len(results)} checks passed.")
    if failures:
        log(f"FAILURES ({len(failures)}):")
        for f in failures:
            log(f"  - {f[0]}: {f[2]}")
        return False
    return True


def run_model_unavailable_checks() -> bool:
    """
    Step 8: Verify safe HTTP 503 behavior when model is uninitialized.
    Starts a separate instance with a non-existent artifact path.
    """
    log("--- Step 8: Safe HTTP 503 Verification (Model Unavailable) ---")
    results: List[Tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        results.append((name, condition, detail))
        status_str = "PASS" if condition else "FAIL"
        log(f"[{status_str}] {name} {detail}")

    env = os.environ.copy()
    env["ENVIRONMENT"] = "production"
    env["API_KEY"] = API_KEY
    env["ALLOWED_ORIGINS"] = "http://localhost:3000"
    env["DEFAULT_MODEL_PATH"] = "models/nonexistent_model.pkl"
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
    ]
    log("Launching second Uvicorn server with uninitialized model...")
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        ready = False
        for _ in range(30):
            time.sleep(0.5)
            s, _, b = make_request("GET", "/api/health/heartbeat")
            if s == 200:
                ready = True
                break

        if not ready:
            log("FAIL: Second server failed to start.")
            return False

        s_live, _, b_live = make_request("GET", "/api/health/heartbeat")
        check(
            "Liveness probe still returns 200 when model is missing",
            s_live == 200 and b_live.get("is_alive") is True,
            f"status={s_live}",
        )

        s_ready, _, b_ready = make_request("GET", "/api/health/ready")
        check(
            "Readiness probe returns HTTP 503 when model is missing",
            s_ready == 503 and b_ready.get("is_ready") is False,
            f"status={s_ready}, body={b_ready}",
        )

        s_pred, _, b_pred = make_request(
            "POST",
            "/api/model/predict",
            headers={"token": API_KEY},
            data={"text": "Any text for inference"},
        )
        check(
            "Predict endpoint returns safe HTTP 503 when model is missing",
            s_pred == 503,
            f"status={s_pred}, body={b_pred}",
        )

        failures = [r for r in results if not r[1]]
        passed_unavail = len(results) - len(failures)
        log(f"Model Unavailable Results: {passed_unavail}/{len(results)} passed.")
        return len(failures) == 0

    finally:
        cleanup_process(proc)


def run_tampered_model_checks() -> bool:
    """
    Step 9: Verify safe HTTP 503 behavior when model SHA-256 digest mismatches (H02).
    Starts an instance with mismatched EXPECTED_MODEL_SHA256 to ensure
    deserialization is safely aborted before loading.
    """
    log("--- Step 9: Model Integrity Verification (SHA-256 Mismatch Fails Closed) ---")
    results: List[Tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        results.append((name, condition, detail))
        status_str = "PASS" if condition else "FAIL"
        log(f"[{status_str}] {name} {detail}")

    env = os.environ.copy()
    env["ENVIRONMENT"] = "production"
    env["API_KEY"] = API_KEY
    env["ALLOWED_ORIGINS"] = "http://localhost:3000"
    # Provide a non-matching SHA-256 digest to simulate a tampered model
    env["EXPECTED_MODEL_SHA256"] = (
        "0000000000000000000000000000000000000000000000000000000000000000"
    )
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
    ]
    log("Launching third Uvicorn server with mismatched model digest...")
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        ready = False
        for _ in range(30):
            time.sleep(0.5)
            s, _, b = make_request("GET", "/api/health/heartbeat")
            if s == 200:
                ready = True
                break

        if not ready:
            log("FAIL: Third server failed to start.")
            return False

        s_ready, _, b_ready = make_request("GET", "/api/health/ready")
        check(
            "Readiness probe returns HTTP 503 when model SHA-256 mismatches",
            s_ready == 503 and b_ready.get("is_ready") is False,
            f"status={s_ready}, body={b_ready}",
        )

        s_pred, _, b_pred = make_request(
            "POST",
            "/api/model/predict",
            headers={"token": API_KEY},
            data={"text": "Any text for inference"},
        )
        check(
            "Predict endpoint returns safe HTTP 503 when model integrity check fails",
            s_pred == 503,
            f"status={s_pred}, body={b_pred}",
        )

        failures = [r for r in results if not r[1]]
        passed_tampered = len(results) - len(failures)
        log(f"Integrity Mismatch Results: {passed_tampered}/{len(results)} passed.")
        return len(failures) == 0

    finally:
        cleanup_process(proc)


def main() -> None:
    start_time = time.time()
    log("Starting PyServe AI API Live End-to-End Verification...")

    env = os.environ.copy()
    env["ENVIRONMENT"] = "production"
    env["API_KEY"] = API_KEY
    env["ALLOWED_ORIGINS"] = "http://localhost:3000"
    env["RATE_LIMIT_PER_MINUTE"] = "60"
    env["MAX_REQUEST_BYTES"] = "65536"
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
    ]
    log(f"Launching Uvicorn server: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Wait for server to start with bounded timeout
        ready = False
        log("Waiting for server liveness probe...")
        for attempt in range(30):
            time.sleep(0.5)
            s, _, b = make_request("GET", "/api/health/heartbeat")
            if s == 200:
                ready = True
                log(f"Server is ready after {(attempt + 1) * 0.5:.1f}s.")
                break

        if not ready:
            log("ERROR: Uvicorn server failed to become ready within 15 seconds.")
            sys.exit(1)

        log("Server confirmed running. Beginning test cases...")
        success_normal = run_checks()

    finally:
        cleanup_process(proc)
        time.sleep(1.0)

    # Run the model unavailable tests on a fresh server instance
    success_unavailable = run_model_unavailable_checks()
    time.sleep(1.0)

    # Run the tampered model tests on a fresh server instance
    success_tampered = run_tampered_model_checks()

    total_time = time.time() - start_time
    log(f"\nTotal Live E2E Execution Time: {total_time:.2f} seconds.")

    if success_normal and success_unavailable and success_tampered:
        log("ALL END-TO-END VERIFICATION CHECKS COMPLETED AND PASSED!")
        sys.exit(0)
    else:
        log("ONE OR MORE END-TO-END CHECKS FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
