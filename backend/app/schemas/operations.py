"""Pydantic schemas for operations endpoints."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from pydantic import BaseModel, Field


class PendingItem(BaseModel):
    id: str
    rider_id: str
    type: str  # approval or escalation
    amount: Optional[float] = None  # rupees, for approvals
    reason: str
    created_at: str  # ISO time
    # Extra context for ops dashboard
    dispute_id: Optional[str] = None
    trip_id: Optional[str] = None
    agent_reasoning: Optional[str] = None


class ApprovalDecision(BaseModel):
    operator_id: str = Field(default="ops_dev", description="Operator identity")
    comments: str = Field(..., min_length=1, description="Mandatory operator comments")


class DisputeDetail(BaseModel):
    id: str
    rider_id: str
    dispute_type: str
    trip_id: Optional[str] = None
    delivery_date: Optional[str] = None
    expected_amount: Optional[float] = None
    actual_paid: Optional[float] = None
    amount_owed: Optional[float] = None
    status: str
    agent_notes: Optional[str] = None
    created_at: str


class ConversationSummary(BaseModel):
    id: str
    rider_id: str
    state: str
    message_count: int
    dispute_count: int
    last_activity: str
    latest_message: Optional[str] = None


class DashboardStats(BaseModel):
    total_disputes: int
    resolved_disputes: int
    pending_approvals: int
    escalated_disputes: int
    total_amount_owed: float
    total_amount_paid: float
