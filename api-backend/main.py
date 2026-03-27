import logging
import uuid
from contextlib import asynccontextmanager
import time as _time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from core.limiter import limiter
from core.logging import configure_logging, cid
from routers.extract import router as extract_router
from routers.requests import router as requests_router
from models.database import create_tables, migrate_schema
import models.orm_models  # noqa: F401 — register ORM models before create_tables

logger = logging.getLogger("api-backend")


@asynccontextmanager
async def lifespan(_: FastAPI):
	configure_logging()
	try:
		create_tables()
		migrate_schema()
	except Exception as exc:
		logger.critical("Failed to initialise database: %s", exc)
		raise
	logger.info("Starting %s v%s in %s mode", settings.app_name, settings.app_version, settings.environment)
	yield
	logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
	app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

	app.state.limiter = limiter
	app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

	@app.exception_handler(Exception)
	async def _unhandled_exception_handler(request: Request, exc: Exception):
		logger.exception("Unhandled error on %s %s", request.method, request.url.path)
		return JSONResponse({"detail": "Internal server error"}, status_code=500)

	_MAX_BODY_BYTES = 15 * 1024 * 1024  # 15 MB (covers 10 MB PDF + JSON overhead)

	class _BodySizeLimitMiddleware(BaseHTTPMiddleware):
		async def dispatch(self, request: Request, call_next):
			cl = request.headers.get("content-length")
			if cl and int(cl) > _MAX_BODY_BYTES:
				return JSONResponse({"detail": "Request body too large"}, status_code=413)
			return await call_next(request)

	app.add_middleware(_BodySizeLimitMiddleware)
	app.add_middleware(
		CORSMiddleware,
		allow_origins=settings.allowed_origins,
		allow_credentials=True,
		allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
		allow_headers=["Content-Type", "Accept", "Idempotency-Key"],
	)

	# ── Idempotency cache (in-memory, 10-minute TTL) ────────────────────
	_idempotency_cache: dict[str, tuple[float, int, bytes, str, dict]] = {}  # key → (ts, status, body, content_type, headers)
	_IDEMPOTENCY_TTL = 600  # seconds

	@app.middleware("http")
	async def _idempotency_middleware(request: Request, call_next):
		cid.set(uuid.uuid4().hex[:8])

		idem_key = request.headers.get("idempotency-key")
		if request.method != "POST" or not idem_key:
			return await call_next(request)

		# Remove expired entries
		now = _time.monotonic()
		expired = [k for k, (ts, *_) in _idempotency_cache.items() if now - ts > _IDEMPOTENCY_TTL]
		for k in expired:
			del _idempotency_cache[k]

		# Return cached response if key seen before
		if idem_key in _idempotency_cache:
			_, status, body, ct, headers = _idempotency_cache[idem_key]
			logger.info("Idempotency cache hit for key=%s", idem_key[:16])
			return Response(content=body, status_code=status, media_type=ct, headers=headers)

		# Process and cache
		response = await call_next(request)
		if 200 <= response.status_code < 300:
			body = b""
			async for chunk in response.body_iterator:
				body += chunk if isinstance(chunk, bytes) else chunk.encode()
			# Store headers (excluding content-length since body size changed)
			headers_dict = dict(response.headers)
			headers_dict.pop("content-length", None)
			_idempotency_cache[idem_key] = (now, response.status_code, body, response.media_type or "application/json", headers_dict)
			return Response(content=body, status_code=response.status_code, media_type=response.media_type, headers=headers_dict)
		return response

	app.include_router(extract_router)
	app.include_router(requests_router)

	@app.get("/api/v1/health")
	async def health() -> dict[str, str]:
		return {"status": "ok"}

	return app


app = create_app()
