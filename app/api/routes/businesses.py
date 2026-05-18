from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import Business, PlatformCredential, Post, PostDelivery
from app.core.orchestrator import run_post_cycle

router = APIRouter(prefix="/api/businesses", tags=["businesses"])


def _guard(request: Request):
    """Block unauthenticated access to all business API routes."""
    if not get_current_user(request):
        raise HTTPException(status_code=401, detail="Not authenticated")


@router.post("")
async def create_business(
    request: Request,
    name: str = Form(...),
    description: str = Form(...),
    industry: str = Form(...),
    location: str = Form(""),
    phone: str = Form(""),
    website_url: str = Form(""),
    brand_color_primary: str = Form("#1a73e8"),
    brand_color_secondary: str = Form("#ffffff"),
    tone: str = Form("professional"),
    target_audience: str = Form(""),
    services: str = Form(""),
    posting_days: str = Form("tuesday,friday"),
    posting_time: str = Form("10:00"),
    timezone: str = Form("America/Chicago"),
    db: AsyncSession = Depends(get_db),
):
    _guard(request)
    biz = Business(
        name=name, description=description, industry=industry,
        location=location, phone=phone, website_url=website_url,
        brand_color_primary=brand_color_primary,
        brand_color_secondary=brand_color_secondary,
        tone=tone, target_audience=target_audience, services=services,
        posting_days=posting_days, posting_time=posting_time, timezone=timezone,
    )
    db.add(biz)
    await db.commit()
    return RedirectResponse(url=f"/dashboard/business/{biz.id}", status_code=303)


@router.post("/{business_id}/edit")
async def edit_business(
    request: Request,
    business_id: int,
    name: str = Form(...),
    description: str = Form(...),
    industry: str = Form(...),
    location: str = Form(""),
    phone: str = Form(""),
    website_url: str = Form(""),
    brand_color_primary: str = Form("#1a73e8"),
    brand_color_secondary: str = Form("#ffffff"),
    tone: str = Form("professional"),
    target_audience: str = Form(""),
    services: str = Form(""),
    posting_days: str = Form("tuesday,friday"),
    posting_time: str = Form("10:00"),
    timezone: str = Form("America/Chicago"),
    db: AsyncSession = Depends(get_db),
):
    _guard(request)
    result = await db.execute(select(Business).where(Business.id == business_id))
    biz = result.scalar_one_or_none()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    biz.name = name
    biz.description = description
    biz.industry = industry
    biz.location = location
    biz.phone = phone
    biz.website_url = website_url
    biz.brand_color_primary = brand_color_primary
    biz.brand_color_secondary = brand_color_secondary
    biz.tone = tone
    biz.target_audience = target_audience
    biz.services = services
    biz.posting_days = posting_days
    biz.posting_time = posting_time
    biz.timezone = timezone
    await db.commit()
    return RedirectResponse(url=f"/dashboard/business/{business_id}", status_code=303)


@router.post("/{business_id}/platforms")
async def add_platform(
    request: Request,
    business_id: int,
    platform: str = Form(...),
    credentials_json: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    _guard(request)
    import json
    cred = PlatformCredential(
        business_id=business_id,
        platform=platform,
        credentials=json.loads(credentials_json),
    )
    db.add(cred)
    await db.commit()
    return RedirectResponse(url=f"/dashboard/business/{business_id}", status_code=303)


@router.post("/{business_id}/post-now")
async def trigger_post(request: Request, business_id: int, db: AsyncSession = Depends(get_db)):
    _guard(request)
    result = await db.execute(select(Business).where(Business.id == business_id))
    biz = result.scalar_one_or_none()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    await run_post_cycle(business_id=business_id)
    return RedirectResponse(url=f"/dashboard/business/{business_id}", status_code=303)


@router.post("/{business_id}/collect-metrics")
async def trigger_metrics(request: Request, business_id: int):
    _guard(request)
    from app.core.metrics import collect_metrics
    await collect_metrics()
    return RedirectResponse(url=f"/dashboard/business/{business_id}", status_code=303)


@router.post("/{business_id}/toggle")
async def toggle_business(request: Request, business_id: int, db: AsyncSession = Depends(get_db)):
    _guard(request)
    result = await db.execute(select(Business).where(Business.id == business_id))
    biz = result.scalar_one_or_none()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    biz.is_active = not biz.is_active
    await db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/platforms/{platform_id}/delete")
async def delete_platform(request: Request, platform_id: int, db: AsyncSession = Depends(get_db)):
    _guard(request)
    result = await db.execute(select(PlatformCredential).where(PlatformCredential.id == platform_id))
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Platform not found")
    biz_id = cred.business_id
    await db.delete(cred)
    await db.commit()
    return RedirectResponse(url=f"/dashboard/business/{biz_id}", status_code=303)
