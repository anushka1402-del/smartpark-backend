from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db, SlotTable
from models.models import SlotCreate, ParkingSlot, SlotStatus
from middleware.auth import require_admin, get_current_user

router = APIRouter()


def slot_to_dict(row: SlotTable) -> dict:
    return {
        "id":           row.id,
        "slot_number":  row.slot_number,
        "location":     row.location,
        "vehicle_type": row.vehicle_type,
        "status":       row.status,
        "created_at":   str(row.created_at),
    }


@router.get("/")
async def get_all_slots(
    current_user: dict       = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db)
):
    """Get all slots. Any logged-in user."""
    result = await db.execute(select(SlotTable).order_by(SlotTable.slot_number))
    slots  = result.scalars().all()
    return [slot_to_dict(s) for s in slots]


@router.post("/", status_code=201, dependencies=[require_admin])
async def create_slot(req: SlotCreate, db: AsyncSession = Depends(get_db)):
    """Create a new parking slot. Admin only."""
    result = await db.execute(select(SlotTable).where(SlotTable.slot_number == req.slot_number))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Slot '{req.slot_number}' already exists.")

    slot = SlotTable(
        slot_number  = req.slot_number,
        location     = req.location,
        vehicle_type = req.vehicle_type,
        status       = "available",
    )
    db.add(slot)
    await db.flush()
    return {"message": "Slot created.", "slot_id": slot.id}


@router.delete("/{slot_id}", dependencies=[require_admin])
async def delete_slot(slot_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a slot. Admin only. Cannot delete if booked or occupied."""
    result   = await db.execute(select(SlotTable).where(SlotTable.id == slot_id))
    slot_row = result.scalar_one_or_none()

    if not slot_row:
        raise HTTPException(status_code=404, detail="Slot not found.")
    if slot_row.status != "available":
        raise HTTPException(status_code=400, detail="Cannot delete a slot that is booked or occupied.")

    await db.delete(slot_row)
    return {"message": f"Slot '{slot_row.slot_number}' deleted."}


@router.post("/seed", status_code=201, dependencies=[require_admin])
async def seed_slots(db: AsyncSession = Depends(get_db)):
    """Seed 20 demo slots. Admin only. Clears existing slots first."""

    # Delete existing slots
    result = await db.execute(select(SlotTable))
    for row in result.scalars().all():
        await db.delete(row)
    await db.flush()

    locations = ["Block A", "Block B", "Block C", "Block D"]
    for i in range(1, 21):
        slot = SlotTable(
            slot_number  = f"P{i:02d}",
            location     = locations[(i - 1) // 5],
            vehicle_type = "car",
            status       = "available",
        )
        db.add(slot)

    return {"message": "20 demo slots created.", "count": 20}
