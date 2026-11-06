"""Rider model - seeded from data/riders.csv."""
import datetime
from sqlalchemy import String, Date, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Rider(Base):
    __tablename__ = "riders"

    rider_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    joined_on: Mapped[datetime.date] = mapped_column(Date)

    # Relationships
    conversations: Mapped[list["Conversation"]] = relationship(  # noqa: F821
        "Conversation", back_populates="rider", lazy="dynamic"
    )

    __table_args__ = (Index("ix_riders_rider_id", "rider_id"),)

    def __repr__(self) -> str:
        return f"<Rider {self.rider_id} {self.name}>"
