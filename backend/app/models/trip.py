"""Trip model - seeded from data/trips.csv."""
import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Trip(Base):
    __tablename__ = "trips"

    trip_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    rider_id: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30))  # completed, cancelled_by_customer, cancelled_by_rider
    distance_km: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    surge_multiplier: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("1.0"))

    __table_args__ = (
        Index("ix_trips_rider_id", "rider_id"),
        Index("ix_trips_started_at", "started_at"),
        Index("ix_trips_rider_date", "rider_id", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<Trip {self.trip_id} rider={self.rider_id} status={self.status}>"
