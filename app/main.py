import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app.core.database import init_db
from app.core.scheduler import start_scheduler
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.businesses import router as businesses_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    yield


app = FastAPI(title="SocialAutoPost", lifespan=lifespan)
app.include_router(dashboard_router)
app.include_router(businesses_router)


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")
