from datetime import datetime
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
