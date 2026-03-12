from datetime import datetime
from typing import Any
from pydantic import BaseModel


class ChatRequest(BaseModel):
    conversation_id: str
    message: str


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    last_message_at: datetime
    message_count: int


class BriefingChange(BaseModel):
    tool: str
    reason: str
    result: dict[str, Any] | None = None
    workout_id: int | None = None
    scheduled_date: str | None = None
    new_date: str | None = None
    workout_type: str | None = None
    title: str | None = None


class BriefingOut(BaseModel):
    date: str
    content: str
    changes_made: list[BriefingChange] | None = None
    generated_at: str | None = None
    status: str = "completed"
