import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers import campaigns

logger = logging.getLogger(__name__)

app = FastAPI(title="Keitaro Campaign Creator")

app.include_router(campaigns.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error while processing %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.mount("/", StaticFiles(directory="static", html=True), name="static")
