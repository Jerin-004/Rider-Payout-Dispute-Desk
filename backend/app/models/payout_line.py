"""PayoutLine model - seeded from data/payout_lines.csv."""
import datetime
from decimal import Decimal
from sqlalchemy import String, Date, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PayoutLine(Base):
    __tablename__ = "payout_lines"

    line_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    payout_date: Mapped[datetime.date] = mapped_column(Date)
    rider_id: Mapped[str] = mapped_column(String(20))
    line_type: Mapped[str] = mapped_column(String(30))  # trip, daily_incentive, cancellation_penalty
    trip_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    __table_args__ = (
        Index("ix_payout_lines_rider_id", "rider_id"),
        Index("ix_payout_lines_trip_id", "trip_id"),
        Index("ix_payout_lines_rider_date", "rider_id", "payout_date"),
    )

    def __repr__(self) -> str:
        return f"<PayoutLine {self.line_id} rider={self.rider_id} type={self.line_type} amount={self.amount}>"
