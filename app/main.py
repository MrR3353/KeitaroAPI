from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import campaigns

app = FastAPI(title="Keitaro Campaign Creator")

app.include_router(campaigns.router)

app.mount("/", StaticFiles(directory="static", html=True), name="static")
