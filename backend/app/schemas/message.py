"""Pydantic schemas for the messages API."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class IncomingMessage(BaseModel):
    message_id: str = Field(..., description="Vendor-assigned unique message ID")
    rider_id: str = Field(..., description="Rider identifier from phone number")
    text: str = Field(..., min_length=1, description="Message text from rider")
    received_at: datetime = Field(..., description="ISO timestamp when message was received")


class MessageReply(BaseModel):
    reply: str = Field(..., description="Text to send back to the rider")


class TraceStep(BaseModel):
    at: str  # ISO time
    type: str  # message_in, tool_call, decision, reply, error
    name: str
    input: Optional[Any] = None
    output: Optional[Any] = None
