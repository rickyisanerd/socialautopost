from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models.models import Business, PlatformCredential, Post, PostDelivery
from app.core.orchestrator import run_post_cycle

router = APIRouter(prefix="/api/businesses", tags=["businesses"])


@router.post("")
async def create_business(
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


@router.post("/{business_id}/platforms")
async def add_platform(
    business_id: int,
    platform: str = Form(...),
    credentials_json: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
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
async def trigger_post(business_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Business).where(Business.id == business_id))
    biz = result.scalar_one_or_none()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    await run_post_cycle(business_id=business_id)
    return RedirectResponse(url=f"/dashboard/business/{business_id}", status_code=303)


@router.post("/{business_id}/toggle")
async def toggle_business(business_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Business).where(Business.id == business_id))
    biz = result.scalar_one_or_none()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    biz.is_active = not biz.is_active
    await db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/platforms/{platform_id}/delete")
async def delete_platform(platform_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PlatformCredential).where(PlatformCredential.id == platform_id))
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Platform not found")
    biz_id = cred.business_id
    await db.delete(cred)
    await db.commit()
    return RedirectResponse(url=f"/dashboard/business/{biz_id}", status_code=303)
