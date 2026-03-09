"""Global middleware: request-id, structured logging, security headers, size limit, rate limiting."""

import logging
import os
import time
import json
import importlib
from collections import defaultdict
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

try:
    import redis
except Exception:  # pragma: no cover
    redis = None

try:
    prometheus_client = importlib.import_module("prometheus_client")
    Counter = prometheus_client.Counter
    Histogram = prometheus_client.Histogram
    CONTENT_TYPE_LATEST = prometheus_client.CONTENT_TYPE_LATEST
    generate_latest = prometheus_client.generate_latest
except Exception:  # pragma: no cover
    Counter = None
    Histogram = None
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    generate_latest = None

logger = logging.getLogger("mds.api")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "120"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
MAX_REQUEST_SIZE_BYTES = int(os.getenv("MAX_REQUEST_SIZE_BYTES", str(2 * 1024 * 1024)))
REDIS_URL = os.getenv("REDIS_URL", "")

TOKEN_BUCKET_CAPACITY = float(RATE_LIMIT_MAX_REQUESTS)
TOKEN_BUCKET_REFILL_PER_SECOND = TOKEN_BUCKET_CAPACITY / max(float(RATE_LIMIT_WINDOW_SECONDS), 1.0)

_requests = defaultdict(lambda: {"tokens": TOKEN_BUCKET_CAPACITY, "ts": time.time()})
_lock = Lock()
_redis_client = None

_metrics_enabled = Counter is not None and Histogram is not None and generate_latest is not None
if _metrics_enabled:
    HTTP_REQUESTS_TOTAL = Counter(
        "mds_http_requests_total",
        "Total number of HTTP requests",
        ["method", "path", "status_code"],
    )
    HTTP_REQUEST_DURATION_SECONDS = Histogram(
        "mds_http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "path"],
    )
    RATE_LIMIT_BLOCKED_TOTAL = Counter(
        "mds_rate_limit_blocked_total",
        "Number of requests blocked by rate limiting",
        ["path"],
    )
else:
    HTTP_REQUESTS_TOTAL = None
    HTTP_REQUEST_DURATION_SECONDS = None
    RATE_LIMIT_BLOCKED_TOTAL = None

if redis is not None and REDIS_URL:
    try:
        _redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=0.2)
        _redis_client.ping()
    except Exception:
        _redis_client = None


def _get_client_key(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token_head = auth_header[7:24]
        return f"bearer:{token_head}"
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"


def _is_rate_limited_with_redis(client_key: str) -> bool | None:
    if _redis_client is None:
        return None

    bucket_key = f"token_bucket:{client_key}"
    now = time.time()
    lua_script = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local refill_rate = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local last_ts = tonumber(data[2])

if tokens == nil then
  tokens = capacity
  last_ts = now
end

local elapsed = now - last_ts
if elapsed < 0 then
  elapsed = 0
end

tokens = math.min(capacity, tokens + (elapsed * refill_rate))
local allowed = 0
if tokens >= requested then
  tokens = tokens - requested
  allowed = 1
end

redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, ttl)
return allowed
"""

    try:
        allowed = _redis_client.eval(
            lua_script,
            1,
            bucket_key,
            now,
            TOKEN_BUCKET_CAPACITY,
            TOKEN_BUCKET_REFILL_PER_SECOND,
            1,
            max(RATE_LIMIT_WINDOW_SECONDS * 2, 10),
        )
        return int(allowed) == 0
    except Exception:
        return None


def _is_rate_limited_in_memory(client_key: str) -> bool:
    now = time.time()
    with _lock:
        bucket = _requests[client_key]
        tokens = bucket["tokens"]
        last_ts = bucket["ts"]
        elapsed = max(now - last_ts, 0.0)
        tokens = min(TOKEN_BUCKET_CAPACITY, tokens + elapsed * TOKEN_BUCKET_REFILL_PER_SECOND)
        if tokens < 1.0:
            bucket["tokens"] = tokens
            bucket["ts"] = now
            return True
        bucket["tokens"] = tokens - 1.0
        bucket["ts"] = now
    return False


def _metrics_path(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


def _record_metrics(request: Request, status_code: int, duration_seconds: float) -> None:
    if not _metrics_enabled:
        return
    path = _metrics_path(request)
    HTTP_REQUESTS_TOTAL.labels(request.method, path, str(status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(request.method, path).observe(max(duration_seconds, 0.0))


def get_metrics_payload() -> tuple[bytes, str]:
    if not _metrics_enabled:
        return b"# prometheus_client not installed\n", CONTENT_TYPE_LATEST
    return generate_latest(), CONTENT_TYPE_LATEST


def configure_middlewares(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_SIZE_BYTES:
                    _record_metrics(request, 413, 0.0)
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Payload too large"},
                        headers={"X-Request-ID": request_id},
                    )
            except ValueError:
                pass

        limiter_key = _get_client_key(request)
        redis_limited = _is_rate_limited_with_redis(limiter_key)
        in_memory_limited = False
        if redis_limited is None:
            in_memory_limited = _is_rate_limited_in_memory(limiter_key)

        if redis_limited or in_memory_limited:
            if _metrics_enabled:
                RATE_LIMIT_BLOCKED_TOTAL.labels(_metrics_path(request)).inc()
            _record_metrics(request, 429, 0.0)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"X-Request-ID": request_id},
            )

        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        _record_metrics(request, response.status_code, duration_ms / 1000.0)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "client": request.client.host if request.client else "unknown",
                },
                ensure_ascii=False,
            )
        )
        return response
