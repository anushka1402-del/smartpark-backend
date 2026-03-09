from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database import get_db, BookingTable, SlotTable, BillTable, UserTable
from models.models import Booking, Bill, BookingCreate, BookingStatus
from middleware.auth import get_current_user, require_staff
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
router = APIRouter()


def booking_to_dict(row: BookingTable, slot_number: str = "", user_email: str = "") -> dict:
    return {
        "id":             row.id,
        "user_id":        row.user_id,
        "slot_id":        row.slot_id,
        "slot_number":    slot_number,
        "user_email":     user_email,
        "status":         row.status,
        "check_in_time":  str(row.check_in_time)  if row.check_in_time  else None,
        "check_out_time": str(row.check_out_time) if row.check_out_time else None,
        "created_at":     str(row.created_at),
    }

def bill_to_dict(row: BillTable) -> dict:
    return {
        "id":             row.id,
        "booking_id":     row.booking_id,
        "slot_number":    row.slot_number,
        "check_in":       str(row.check_in),
        "check_out":      str(row.check_out),
        "rate_per_hour":  row.rate_per_hour,
        "duration_hours": row.duration_hours,
        "amount":         row.amount,
        "created_at":     str(row.created_at),
    }


@router.post("/", status_code=201)
async def create_booking(
    req:          BookingCreate,
    current_user: dict          = Depends(get_current_user),
    db:           AsyncSession  = Depends(get_db)
):
    """Book a slot. One active booking per user at a time."""

    # Rule: one active booking per user
    existing = await db.execute(
        select(BookingTable).where(
            and_(
                BookingTable.user_id == current_user["user_id"],
                BookingTable.status.in_(["pending", "active"])
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400,
            detail="You already have an active booking. Cancel it before booking again.")

    # Fetch slot
    result   = await db.execute(select(SlotTable).where(SlotTable.id == req.slot_id))
    slot_row = result.scalar_one_or_none()
    if not slot_row:
        raise HTTPException(status_code=404, detail="Slot not found.")
    if slot_row.status != "available":
        raise HTTPException(status_code=400,
            detail=f"Slot '{slot_row.slot_number}' is not available (status: {slot_row.status}).")

    # Create booking
    booking = BookingTable(
        user_id = current_user["user_id"],
        slot_id = req.slot_id,
        status  = "pending",
    )
    db.add(booking)

    # Transition slot: available → booked
    slot_row.status = "booked"

    await db.flush()
    return {"message": "Slot booked successfully.", "booking_id": booking.id}


@router.get("/my")
async def my_bookings(
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db)
):
    """Get all bookings for the current user."""
    result = await db.execute(
        select(BookingTable, SlotTable.slot_number)
        .join(SlotTable, BookingTable.slot_id == SlotTable.id)
        .where(BookingTable.user_id == current_user["user_id"])
        .order_by(BookingTable.created_at.desc())
    )
    rows = result.all()
    return [booking_to_dict(b, sn, current_user["email"]) for b, sn in rows]


@router.get("/all", dependencies=[require_staff])
async def all_bookings(db: AsyncSession = Depends(get_db)):
    """All bookings in the system. Staff and Admin only."""
    result = await db.execute(
        select(BookingTable, SlotTable.slot_number, UserTable.email)
        .join(SlotTable,   BookingTable.slot_id  == SlotTable.id)
        .join(UserTable,   BookingTable.user_id  == UserTable.id)
        .order_by(BookingTable.created_at.desc())
    )
    rows = result.all()
    return [booking_to_dict(b, sn, email) for b, sn, email in rows]


@router.delete("/{booking_id}")
async def cancel_booking(
    booking_id:   int,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db)
):
    """Cancel a booking. Only owner or admin. Only before check-in."""
    result      = await db.execute(select(BookingTable).where(BookingTable.id == booking_id))
    booking_row = result.scalar_one_or_none()
    if not booking_row:
        raise HTTPException(status_code=404, detail="Booking not found.")

    is_admin = current_user["role"] == "admin"
    if booking_row.user_id != current_user["user_id"] and not is_admin:
        raise HTTPException(status_code=403, detail="You can only cancel your own bookings.")

    # Use OOP class to enforce the business rule
    booking = Booking(booking_row.user_id, booking_row.slot_id)
    booking.status = BookingStatus(booking_row.status)
    try:
        booking.cancel()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    booking_row.status = "cancelled"

    # Free the slot: → available
    slot_result = await db.execute(select(SlotTable).where(SlotTable.id == booking_row.slot_id))
    slot_row    = slot_result.scalar_one_or_none()
    if slot_row:
        slot_row.status = "available"

    return {"message": "Booking cancelled. Slot is now available."}


@router.post("/{booking_id}/checkin", dependencies=[require_staff])
async def check_in(booking_id: int, db: AsyncSession = Depends(get_db)):
    """Check in a vehicle. Staff only. Slot → occupied."""
    result      = await db.execute(select(BookingTable).where(BookingTable.id == booking_id))
    booking_row = result.scalar_one_or_none()
    if not booking_row:
        raise HTTPException(status_code=404, detail="Booking not found.")

    # OOP class validates state
    booking = Booking(booking_row.user_id, booking_row.slot_id)
    booking.status = BookingStatus(booking_row.status)
    try:
        booking.check_in()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    booking_row.status        = "active"
    booking_row.check_in_time = datetime.utcnow()

    # Slot: booked → occupied
    slot_result = await db.execute(select(SlotTable).where(SlotTable.id == booking_row.slot_id))
    slot_row    = slot_result.scalar_one_or_none()
    if slot_row:
        slot_row.status = "occupied"

    return {"message": "Check-in successful. Slot is now occupied."}


@router.post("/{booking_id}/checkout", dependencies=[require_staff])
async def check_out(booking_id: int, db: AsyncSession = Depends(get_db)):
    """Check out a vehicle. Staff only. Bill auto-generated."""
    result      = await db.execute(select(BookingTable).where(BookingTable.id == booking_id))
    booking_row = result.scalar_one_or_none()
    if not booking_row:
        raise HTTPException(status_code=404, detail="Booking not found.")

    # OOP class validates state
    booking = Booking(booking_row.user_id, booking_row.slot_id)
    booking.status = BookingStatus(booking_row.status)
    try:
        booking.check_out()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    check_out_time = datetime.utcnow()
    booking_row.status         = "completed"
    booking_row.check_out_time = check_out_time

    # Slot: occupied → available
    slot_result = await db.execute(select(SlotTable).where(SlotTable.id == booking_row.slot_id))
    slot_row    = slot_result.scalar_one_or_none()
    slot_number = slot_row.slot_number if slot_row else "?"
    if slot_row:
        slot_row.status = "available"

    # Auto-generate Bill using OOP class
    rate = float(os.getenv("RATE_PER_HOUR", 50.0))
    bill = Bill(
        booking_id    = booking_id,
        user_id       = booking_row.user_id,
        slot_number   = slot_number,
        check_in      = booking_row.check_in_time,
        check_out     = check_out_time,
        rate_per_hour = rate,
    )
    bill_row = BillTable(
        booking_id     = bill.booking_id,
        user_id        = bill.user_id,
        slot_number    = bill.slot_number,
        check_in       = bill.check_in,
        check_out      = bill.check_out,
        rate_per_hour  = bill.rate_per_hour,
        duration_hours = bill.duration_hours,
        amount         = bill.amount,
    )
    db.add(bill_row)
    await db.flush()

    return {
        "message":        "Check-out successful. Bill generated.",
        "bill_id":        bill_row.id,
        "duration_hours": bill.duration_hours,
        "amount":         bill.amount,
        "rate_per_hour":  bill.rate_per_hour,
    }


@router.get("/bills/my")
async def my_bills(
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db)
):
    """Get all bills for the current user."""
    result = await db.execute(
        select(BillTable)
        .where(BillTable.user_id == current_user["user_id"])
        .order_by(BillTable.created_at.desc())
    )
    bills = result.scalars().all()
    return [bill_to_dict(b) for b in bills]
