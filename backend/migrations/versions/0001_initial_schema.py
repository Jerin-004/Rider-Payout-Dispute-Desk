"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-06 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "riders",
        sa.Column("rider_id", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("joined_on", sa.Date(), nullable=False),
    )
    op.create_index("ix_riders_rider_id", "riders", ["rider_id"])

    op.create_table(
        "trips",
        sa.Column("trip_id", sa.String(20), primary_key=True),
        sa.Column("rider_id", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("distance_km", sa.Numeric(8, 2), nullable=False),
        sa.Column("surge_multiplier", sa.Numeric(5, 2), nullable=False, server_default="1.0"),
    )
    op.create_index("ix_trips_rider_id", "trips", ["rider_id"])
    op.create_index("ix_trips_started_at", "trips", ["started_at"])
    op.create_index("ix_trips_rider_date", "trips", ["rider_id", "started_at"])

    op.create_table(
        "payout_lines",
        sa.Column("line_id", sa.String(20), primary_key=True),
        sa.Column("payout_date", sa.Date(), nullable=False),
        sa.Column("rider_id", sa.String(20), nullable=False),
        sa.Column("line_type", sa.String(30), nullable=False),
        sa.Column("trip_id", sa.String(20), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
    )
    op.create_index("ix_payout_lines_rider_id", "payout_lines", ["rider_id"])
    op.create_index("ix_payout_lines_trip_id", "payout_lines", ["trip_id"])
    op.create_index("ix_payout_lines_rider_date", "payout_lines", ["rider_id", "payout_date"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rider_id", sa.String(20), sa.ForeignKey("riders.rider_id"), nullable=False),
        sa.Column("state", sa.String(30), nullable=False, server_default="NEW"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversations_rider_id", "conversations", ["rider_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("message_id", sa.String(200), nullable=False, unique=True),
        sa.Column("rider_id", sa.String(20), nullable=False),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reply_text", sa.Text(), nullable=True),
        sa.Column("intent", sa.String(50), nullable=True),
        sa.Column("extracted_entities", sa.JSON(), nullable=True),
        sa.Column("agent_analysis", sa.JSON(), nullable=True),
    )
    op.create_index("ix_messages_rider_id", "messages", ["rider_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_unique_constraint("uq_messages_message_id", "messages", ["message_id"])

    op.create_table(
        "disputes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rider_id", sa.String(20), nullable=False),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("dispute_type", sa.String(50), nullable=False),
        sa.Column("trip_id", sa.String(20), nullable=True),
        sa.Column("delivery_date", sa.Date(), nullable=True),
        sa.Column("claimed_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("expected_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("actual_paid", sa.Numeric(10, 2), nullable=True),
        sa.Column("amount_owed", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"),
        sa.Column("agent_notes", sa.Text(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_disputes_rider_id", "disputes", ["rider_id"])
    op.create_index("ix_disputes_conversation_id", "disputes", ["conversation_id"])
    op.create_index("ix_disputes_trip_id", "disputes", ["trip_id"])
    op.create_index("ix_disputes_status", "disputes", ["status"])

    op.create_table(
        "payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dispute_id", sa.String(36), sa.ForeignKey("disputes.id"), nullable=False),
        sa.Column("rider_id", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("payswift_payout_id", sa.String(200), nullable=True),
        sa.Column("payswift_status", sa.String(50), nullable=True),
        sa.Column("payswift_reference", sa.String(200), nullable=True),
        sa.Column("payswift_response", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("initiated_by", sa.String(50), nullable=False, server_default="auto"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payments_dispute_id", "payments", ["dispute_id"])
    op.create_index("ix_payments_rider_id", "payments", ["rider_id"])
    op.create_index("ix_payments_rider_created", "payments", ["rider_id", "created_at"])
    op.create_unique_constraint("uq_payments_idempotency_key", "payments", ["idempotency_key"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dispute_id", sa.String(36), sa.ForeignKey("disputes.id"), nullable=False),
        sa.Column("rider_id", sa.String(20), nullable=False),
        sa.Column("approval_type", sa.String(30), nullable=False, server_default="approval"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("agent_reasoning", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("operator_id", sa.String(100), nullable=True),
        sa.Column("operator_comments", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_approvals_dispute_id", "approvals", ["dispute_id"])
    op.create_index("ix_approvals_rider_id", "approvals", ["rider_id"])
    op.create_index("ix_approvals_status", "approvals", ["status"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("rider_id", sa.String(20), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("dispute_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_audit_events_conversation_id", "audit_events", ["conversation_id"])
    op.create_index("ix_audit_events_rider_id", "audit_events", ["rider_id"])
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("approvals")
    op.drop_table("payments")
    op.drop_table("disputes")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("payout_lines")
    op.drop_table("trips")
    op.drop_table("riders")
