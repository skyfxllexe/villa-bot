# database/models.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import json

Base = declarative_base()

# ─── Хозяева ──────────────────────────────────────
class Owner(Base):
    __tablename__ = "owners"

    id            = Column(Integer, primary_key=True)
    telegram_id   = Column(Integer, unique=True, nullable=False)
    username      = Column(String, nullable=True)
    first_name    = Column(String, nullable=True)
    is_active     = Column(Boolean, default=True)
    commission    = Column(Float, default=5.0)  # % комиссии
    created_at    = Column(DateTime, default=datetime.utcnow)

    villas        = relationship("Villa", back_populates="owner", cascade = "all, delete-orphan")
    invite_codes  = relationship("InviteCode", back_populates="owner")

# ─── Инвайт-коды ──────────────────────────────────
class InviteCode(Base):
    __tablename__ = "invite_codes"

    id            = Column(Integer, primary_key=True)
    code          = Column(String, unique=True, nullable=False)
    owner_id      = Column(Integer, ForeignKey("owners.id"), nullable=True)
    is_used       = Column(Boolean, default=False)
    used_at       = Column(DateTime, nullable=True)
    expires_at    = Column(DateTime, nullable=True)  # срок действия
    created_at    = Column(DateTime, default=datetime.utcnow)

    owner         = relationship("Owner", back_populates="invite_codes")

# ─── Виллы ────────────────────────────────────────
class Villa(Base):
    __tablename__ = "villas"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    owner_id      = Column(Integer, ForeignKey("owners.id"), nullable=False)
    name          = Column(String, nullable=False)
    location      = Column(String, nullable=False)
    price_idr     = Column(Float, nullable=False)
    guests        = Column(Integer, nullable=False)
    bedrooms      = Column(Integer, nullable=False)
    description   = Column(Text, nullable=True)
    features      = Column(Text, nullable=True)   # JSON
    rules         = Column(Text, nullable=True)
    photos        = Column(Text, nullable=True)   # JSON file_ids
    client_photos = Column(Text, nullable=True)         # ← новое! file_id второго бота
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    owner         = relationship("Owner", back_populates="villas")
    bookings      = relationship("Booking", back_populates="villa")

    def to_dict(self):
        return {
            "id":          self.id,
            "owner_id":    self.owner_id,

            "name":        self.name,
            "location":    self.location,
            "price_idr":   self.price_idr,
            "price_usd":   round(self.price_idr / 16000),
            "guests":      self.guests,
            "bedrooms":    self.bedrooms,
            "description": self.description,
            "features":    json.loads(self.features or "[]"),
            "rules":       self.rules,
            "photos":      json.loads(self.photos or "[]"),
            "is_active":   self.is_active,
        }

# ─── Брони ────────────────────────────────────────
class Booking(Base):
    __tablename__ = "bookings"
    
    id            = Column(Integer, primary_key=True)
    villa_id      = Column(Integer, ForeignKey("villas.id"))
    client_tg_id  = Column(Integer, nullable=False)
    client_name   = Column(String, nullable=True)
    client_phone  = Column(String, nullable=True)
    checkin       = Column(DateTime, nullable=False)
    checkout      = Column(DateTime, nullable=False)
    status        = Column(String, default="pending")  # pending/confirmed/cancelled
    commission    = Column(Float, nullable=True)       # сумма комиссии
    created_at    = Column(DateTime, default=datetime.utcnow)

    villa         = relationship("Villa", back_populates="bookings")