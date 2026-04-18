import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from database.connection import AsyncSessionLocal, init_db
from database.models import Villa, Booking, Owner
from contextlib import asynccontextmanager
from datetime import datetime
import json

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

# ─── CORS ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Все активные виллы ───────────────────────────
@app.get("/villas")
async def get_villas(
    location: str  = None,
    guests: int    = None,
    max_price: int = None
):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Villa, Owner)
            .join(Owner, Villa.owner_id == Owner.id)
            .where(Villa.is_active == True)
        )
        rows = result.all()

    # Фильтры
    if location:
        rows = [r for r in rows if r[0].location == location]
    if guests:
        rows = [r for r in rows if r[0].guests >= guests]
    if max_price:
        rows = [r for r in rows if r[0].price_idr <= max_price]

    villas = []
    for villa, owner in rows:
        d = villa.to_dict()
        d["owner_tg_id"] = owner.telegram_id
        villas.append(d)

    return villas

# ─── Одна вилла ───────────────────────────────────
@app.get("/villas/{villa_id}")
async def get_villa(villa_id: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Villa).where(Villa.id == villa_id)
        )
        villa = result.scalar_one_or_none()

    if not villa:
        raise HTTPException(status_code=404, detail="Вилла не найдена")

    return villa.to_dict()

# ─── Проверка доступности ─────────────────────────
@app.get("/villas/{villa_id}/availability")
async def check_availability(villa_id: int, checkin: str, checkout: str):
    checkin_dt  = datetime.strptime(checkin, "%Y-%m-%d")
    checkout_dt = datetime.strptime(checkout, "%Y-%m-%d")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).where(
                Booking.villa_id == villa_id,
                Booking.status.in_(["pending", "confirmed"]),
                Booking.checkin  < checkout_dt,
                Booking.checkout > checkin_dt
            )
        )
        bookings = result.scalars().all()

    return {"available": len(bookings) == 0}

# ─── Создать бронь ────────────────────────────────
@app.post("/bookings")
async def create_booking(data: dict):
    async with AsyncSessionLocal() as db:
        # Проверяем доступность
        checkin_dt  = datetime.strptime(data["checkin"], "%Y-%m-%d")
        checkout_dt = datetime.strptime(data["checkout"], "%Y-%m-%d")

        result = await db.execute(
            select(Booking).where(
                Booking.villa_id == data["villa_id"],
                Booking.status.in_(["pending", "confirmed"]),
                Booking.checkin  < checkout_dt,
                Booking.checkout > checkin_dt
            )
        )
        existing = result.scalars().all()

        if existing:
            raise HTTPException(status_code=400, detail="Вилла недоступна в эти даты")

        booking = Booking(
            
            villa_id     = data["villa_id"],
            client_tg_id = data["client_tg_id"],
            client_name  = data.get("client_name"),
            client_phone = data.get("client_phone"),
            checkin      = checkin_dt,
            checkout     = checkout_dt,
            status       = "pending"
        )
        db.add(booking)
        await db.commit()
        await db.refresh(booking)

        return {"ok": True, "booking_id": booking.id}

# ─── Healthcheck ──────────────────────────────────
@app.get("/")
async def root():
    return {"status": "ok", "service": "Bali Villa API"}