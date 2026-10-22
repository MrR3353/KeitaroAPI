import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers import campaign_editor, campaigns

logger = logging.getLogger(__name__)


class NoCacheStaticFiles(StaticFiles):
    """Forces the browser to always revalidate static assets instead of relying on
    heuristic disk caching, which otherwise can silently serve a stale app.js/index.html
    after a plain reload (no Cache-Control header is sent by default)."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app = FastAPI(title="Keitaro Campaign Creator")

app.include_router(campaigns.router)
app.include_router(campaign_editor.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error while processing %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.mount("/", NoCacheStaticFiles(directory="static", html=True), name="static")
