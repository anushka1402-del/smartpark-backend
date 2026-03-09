from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import init_db, close_db
from routes import auth, slots, bookings, admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()       # creates MySQL tables on startup
    yield
    await close_db()

app = FastAPI(
    title       = "SmartPark API",
    description = "Smart Campus Parking System — IBM Hackathon",
    version     = "1.0.0",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(auth.router,     prefix="/auth",     tags=["Auth"])
app.include_router(slots.router,    prefix="/slots",    tags=["Slots"])
app.include_router(bookings.router, prefix="/bookings", tags=["Bookings"])
app.include_router(admin.router,    prefix="/admin",    tags=["Admin"])

@app.get("/")
async def root():
    return {"message": "SmartPark API is running 🚗", "docs": "/docs"}
