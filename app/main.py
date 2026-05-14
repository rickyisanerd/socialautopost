import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from app.core.database import init_db
from app.core.scheduler import start_scheduler
from app.core.auth import check_password, create_session_cookie, COOKIE_NAME, SESSION_MAX_AGE
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.businesses import router as businesses_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    yield


Path("generated/images").mkdir(parents=True, exist_ok=True)
Path("generated/videos").mkdir(parents=True, exist_ok=True)
app = FastAPI(title="SocialAutoPost", lifespan=lifespan)
app.include_router(dashboard_router)
app.include_router(businesses_router)


app.mount("/static/images", StaticFiles(directory="generated/images"), name="generated_images")


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if not check_password(username, password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=401,
        )
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_cookie(username),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key=COOKIE_NAME)
    return response
