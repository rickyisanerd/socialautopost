from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import Business, PlatformCredential, Post, PostDelivery

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
async def dashboard_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    result = await db.execute(
        select(Business).options(
            selectinload(Business.platforms),
            selectinload(Business.posts).selectinload(Post.deliveries),
        )
    )
    businesses = result.scalars().all()

    stats = {}
    for biz in businesses:
        total = sum(len(p.deliveries) for p in biz.posts)
        delivered = sum(1 for p in biz.posts for d in p.deliveries if d.status == "delivered")
        failed = sum(1 for p in biz.posts for d in p.deliveries if d.status == "failed")
        stats[biz.id] = {"total": total, "delivered": delivered, "failed": failed, "posts": len(biz.posts)}

    return templates.TemplateResponse("dashboard/home.html", {
        "request": request,
        "businesses": businesses,
        "stats": stats,
    })


@router.get("/business/{business_id}")
async def business_detail(request: Request, business_id: int, db: AsyncSession = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    result = await db.execute(
        select(Business)
        .where(Business.id == business_id)
        .options(
            selectinload(Business.platforms),
            selectinload(Business.posts).selectinload(Post.deliveries),
        )
    )
    biz = result.scalar_one_or_none()
    if not biz:
        return templates.TemplateResponse("dashboard/404.html", {"request": request}, status_code=404)

    recent_posts = sorted(biz.posts, key=lambda p: p.created_at, reverse=True)[:20]

    return templates.TemplateResponse("dashboard/business.html", {
        "request": request,
        "business": biz,
        "posts": recent_posts,
    })


@router.get("/add-business")
async def add_business_form(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("dashboard/add_business.html", {"request": request})
