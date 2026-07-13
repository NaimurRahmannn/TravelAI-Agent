from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ItineraryRecord(Base):
    """Persisted itinerary for a conversation.

    `days` stores the nested day/activity structure as JSON, mirroring
    `app.schemas.itinerary.Itinerary`.
    """

    __tablename__ = "itineraries"

    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    days: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    estimated_total_cost: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
