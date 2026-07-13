from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TripRecord(Base):
    """Persisted trip preferences for a conversation.

    One row per conversation_id; fields mirror `app.schemas.trip.TripPreferences`.
    """

    __tablename__ = "trips"

    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True)
    travel_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    travelers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
