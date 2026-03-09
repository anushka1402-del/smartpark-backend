"""
models/models.py
================
Pure Python OOP classes — no database logic here.
These enforce business rules independently of the DB layer.

Classes:  User, ParkingSlot, Booking, Bill
Schemas:  Pydantic request/response models
"""

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, EmailStr


# ─────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────

class UserRole(str, Enum):
    admin = "admin"
    staff = "staff"
    user  = "user"

class SlotStatus(str, Enum):
    available = "available"
    booked    = "booked"
    occupied  = "occupied"

class BookingStatus(str, Enum):
    pending   = "pending"
    active    = "active"
    completed = "completed"
    cancelled = "cancelled"


# ─────────────────────────────────────────
# OOP CLASS 1: User
# ─────────────────────────────────────────

class User:
    """Represents a registered campus user with a role."""

    def __init__(self, name: str, email: str, password_hash: str, role: UserRole = UserRole.user):
        self.name          = name
        self.email         = email
        self.password_hash = password_hash
        self.role          = role
        self.created_at    = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "name":          self.name,
            "email":         self.email,
            "password_hash": self.password_hash,
            "role":          self.role.value,
            "created_at":    self.created_at,
        }


# ─────────────────────────────────────────
# OOP CLASS 2: ParkingSlot
# ─────────────────────────────────────────

class ParkingSlot:
    """
    A parking slot with a strict state machine.

    Valid transitions:
        available → booked    (user books)
        booked    → occupied  (staff checks in)
        booked    → available (booking cancelled)
        occupied  → available (staff checks out)
    """

    VALID_TRANSITIONS = {
        SlotStatus.available: [SlotStatus.booked],
        SlotStatus.booked:    [SlotStatus.occupied, SlotStatus.available],
        SlotStatus.occupied:  [SlotStatus.available],
    }

    def __init__(self, slot_number: str, location: str, vehicle_type: str = "car"):
        self.slot_number  = slot_number
        self.location     = location
        self.vehicle_type = vehicle_type
        self.status       = SlotStatus.available
        self.created_at   = datetime.utcnow()

    def transition(self, new_status: SlotStatus):
        """Move to a new status. Raises ValueError if the transition is invalid."""
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot move slot '{self.slot_number}' from "
                f"'{self.status.value}' to '{new_status.value}'. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        self.status = new_status


# ─────────────────────────────────────────
# OOP CLASS 3: Booking
# ─────────────────────────────────────────

class Booking:
    """
    Booking lifecycle manager.

    States: pending → active → completed
                    ↘ cancelled  (only from pending)
    """

    def __init__(self, user_id: int, slot_id: int):
        self.user_id        = user_id
        self.slot_id        = slot_id
        self.status         = BookingStatus.pending
        self.check_in_time  = None
        self.check_out_time = None
        self.created_at     = datetime.utcnow()

    def check_in(self):
        """Mark as active. Only valid from pending."""
        if self.status != BookingStatus.pending:
            raise ValueError(
                f"Check-in failed — booking is '{self.status.value}', expected 'pending'."
            )
        self.status        = BookingStatus.active
        self.check_in_time = datetime.utcnow()

    def check_out(self):
        """Mark as completed. Only valid from active."""
        if self.status != BookingStatus.active:
            raise ValueError(
                f"Check-out failed — booking is '{self.status.value}', expected 'active'."
            )
        self.status         = BookingStatus.completed
        self.check_out_time = datetime.utcnow()

    def cancel(self):
        """Cancel booking. Only valid before check-in (pending)."""
        if self.status != BookingStatus.pending:
            raise ValueError(
                f"Cannot cancel — booking is '{self.status.value}'. "
                f"Cancellation is only allowed before check-in."
            )
        self.status = BookingStatus.cancelled


# ─────────────────────────────────────────
# OOP CLASS 4: Bill
# ─────────────────────────────────────────

class Bill:
    """
    Auto-generated bill on checkout.
    Minimum charge: 1 hour regardless of actual duration.
    """

    def __init__(self, booking_id: int, user_id: int, slot_number: str,
                 check_in: datetime, check_out: datetime, rate_per_hour: float):
        self.booking_id     = booking_id
        self.user_id        = user_id
        self.slot_number    = slot_number
        self.check_in       = check_in
        self.check_out      = check_out
        self.rate_per_hour  = rate_per_hour
        self.duration_hours = self._calculate_duration()
        self.amount         = self._calculate_amount()
        self.created_at     = datetime.utcnow()

    def _calculate_duration(self) -> float:
        """Actual hours parked, minimum 1 hour."""
        raw = (self.check_out - self.check_in).total_seconds() / 3600
        return max(round(raw, 2), 1.0)

    def _calculate_amount(self) -> float:
        """Total = duration × rate."""
        return round(self.duration_hours * self.rate_per_hour, 2)


# ─────────────────────────────────────────
# PYDANTIC SCHEMAS  (API request/response)
# ─────────────────────────────────────────

class RegisterRequest(BaseModel):
    name:     str
    email:    EmailStr
    password: str
    role:     UserRole = UserRole.user

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str

class SlotCreate(BaseModel):
    slot_number:  str
    location:     str
    vehicle_type: str = "car"

class BookingCreate(BaseModel):
    slot_id: int

class PricingUpdate(BaseModel):
    rate_per_hour: float
