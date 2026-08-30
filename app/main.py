from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router

app = FastAPI(
    title="Asynchronous E-Commerce Report Engine",
    description=(
        "Ingests high volumes of order events and generates heavy analytical "
        "reports asynchronously."
    ),
    version="1.0.0",
)

app.include_router(router)


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(HTTPException)
async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, list):
        detail: list[object] = exc.detail
    else:
        detail = [{"loc": [], "msg": str(exc.detail), "type": "error"}]
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
