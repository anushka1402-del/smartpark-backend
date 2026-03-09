from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract
from database import get_db, SlotTable, BookingTable, BillTable, UserTable, SettingTable
from models.models import PricingUpdate
from middleware.auth import require_admin
from datetime import datetime

router = APIRouter()


@router.get("/dashboard", dependencies=[require_admin])
async def dashboard(db: AsyncSession = Depends(get_db)):
    """Live stats for admin dashboard."""

    # Slot counts
    total_slots     = (await db.execute(select(func.count()).select_from(SlotTable))).scalar()
    available_slots = (await db.execute(select(func.count()).select_from(SlotTable).where(SlotTable.status == "available"))).scalar()
    booked_slots    = (await db.execute(select(func.count()).select_from(SlotTable).where(SlotTable.status == "booked"))).scalar()
    occupied_slots  = (await db.execute(select(func.count()).select_from(SlotTable).where(SlotTable.status == "occupied"))).scalar()

    # Booking counts
    total_bookings     = (await db.execute(select(func.count()).select_from(BookingTable))).scalar()
    pending_bookings   = (await db.execute(select(func.count()).select_from(BookingTable).where(BookingTable.status == "pending"))).scalar()
    active_bookings    = (await db.execute(select(func.count()).select_from(BookingTable).where(BookingTable.status == "active"))).scalar()
    completed_bookings = (await db.execute(select(func.count()).select_from(BookingTable).where(BookingTable.status == "completed"))).scalar()

    # Total users
    total_users = (await db.execute(select(func.count()).select_from(UserTable))).scalar()

    # Total revenue
    revenue_result = await db.execute(select(func.sum(BillTable.amount)))
    total_revenue  = round(revenue_result.scalar() or 0.0, 2)

    # Current rate from settings
    setting_result = await db.execute(select(SettingTable).where(SettingTable.key == "rate_per_hour"))
    setting_row    = setting_result.scalar_one_or_none()
    rate           = float(setting_row.value) if setting_row else 50.0

    return {
        "slots": {
            "total":     total_slots,
            "available": available_slots,
            "booked":    booked_slots,
            "occupied":  occupied_slots,
        },
        "bookings": {
            "total":     total_bookings,
            "pending":   pending_bookings,
            "active":    active_bookings,
            "completed": completed_bookings,
        },
        "users":         total_users,
        "total_revenue": total_revenue,
        "rate_per_hour": rate,
    }


@router.put("/pricing", dependencies=[require_admin])
async def update_pricing(req: PricingUpdate, db: AsyncSession = Depends(get_db)):
    """Update hourly parking rate. Admin only."""
    if req.rate_per_hour <= 0:
        raise HTTPException(status_code=400, detail="Rate must be greater than 0.")

    result  = await db.execute(select(SettingTable).where(SettingTable.key == "rate_per_hour"))
    setting = result.scalar_one_or_none()

    if setting:
        setting.value      = str(req.rate_per_hour)
        setting.updated_at = datetime.utcnow()
    else:
        db.add(SettingTable(key="rate_per_hour", value=str(req.rate_per_hour)))

    return {"message": f"Rate updated to ₹{req.rate_per_hour}/hour."}


@router.get("/users", dependencies=[require_admin])
async def get_all_users(db: AsyncSession = Depends(get_db)):
    """All registered users. Admin only."""
    result = await db.execute(select(UserTable).order_by(UserTable.created_at.desc()))
    users  = result.scalars().all()
    return [
        {"id": u.id, "name": u.name, "email": u.email,
         "role": u.role, "created_at": str(u.created_at)}
        for u in users
    ]


@router.get("/revenue/monthly", dependencies=[require_admin])
async def monthly_revenue(db: AsyncSession = Depends(get_db)):
    """Monthly revenue for last 6 months."""
    result = await db.execute(
        select(
            extract("year",  BillTable.created_at).label("year"),
            extract("month", BillTable.created_at).label("month"),
            func.sum(BillTable.amount).label("revenue"),
            func.count(BillTable.id).label("total_bookings"),
        )
        .group_by("year", "month")
        .order_by("year", "month")
    )
    rows = result.all()
    return [
        {
            "year":           int(r.year),
            "month":          int(r.month),
            "revenue":        round(r.revenue, 2),
            "total_bookings": r.total_bookings,
        }
        for r in rows[-6:]   # last 6 months
    ]
