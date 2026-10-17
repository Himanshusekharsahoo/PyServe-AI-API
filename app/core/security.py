import secrets
from typing import Optional

from fastapi import HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_401_UNAUTHORIZED

from app.core import config
from app.core.messages import AUTH_REQ

api_key = APIKeyHeader(name="token", auto_error=False)


def validate_request(header: Optional[str] = Security(api_key)) -> bool:
    if (
        header is None
        or config.API_KEY is None
        or not secrets.compare_digest(header, str(config.API_KEY))
    ):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail=AUTH_REQ, headers={}
        )
    return True


def get_client_ip(request: Request) -> str:
    """
    Extracts the client IP address securely.
    If TRUSTED_PROXIES is configured and the direct socket peer matches a
    trusted proxy, client IP is extracted from X-Forwarded-For or X-Real-IP.
    Otherwise, the direct socket peer IP is used, strictly ignoring spoofable
    forwarded headers.
    """
    peer_ip = request.client.host if request.client else "unknown"
    if not config.TRUSTED_PROXIES:
        return peer_ip

    if peer_ip in config.TRUSTED_PROXIES:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            hops = [h.strip() for h in forwarded_for.split(",") if h.strip()]
            if hops:
                return hops[0]
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

    return peer_ip
