import json
import logging
from datetime import date, datetime, timezone

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.database import get_db
from app.models.chat import ChatMessage
from app.schemas.coach import ChatRequest, ChatMessageOut, ConversationSummary, BriefingOut
from app.services.coach_context import build_training_context, build_system_prompt, build_briefing

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_HISTORY_MESSAGES = 20


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            ChatMessage.conversation_id,
            func.min(ChatMessage.content).filter(ChatMessage.role == "user").label("first_msg"),
            func.max(ChatMessage.created_at).label("last_at"),
            func.count(ChatMessage.id).label("msg_count"),
        )
        .group_by(ChatMessage.conversation_id)
        .order_by(func.max(ChatMessage.created_at).desc())
    )

    conversations = []
    for row in result.all():
        title = (row.first_msg or "New conversation")[:60]
        conversations.append(
            ConversationSummary(
                conversation_id=row.conversation_id,
                title=title,
                last_message_at=row.last_at,
                message_count=row.msg_count,
            )
        )
    return conversations


@router.get("/conversations/{conversation_id}", response_model=list[ChatMessageOut])
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at)
    )
    return [ChatMessageOut.model_validate(m) for m in result.scalars().all()]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.conversation_id == conversation_id)
    )
    messages = result.scalars().all()
    for m in messages:
        await db.delete(m)
    await db.commit()
    return {"status": "deleted"}


@router.get("/briefing", response_model=BriefingOut)
async def get_briefing(db: AsyncSession = Depends(get_db)):
    """Generate a personalized morning briefing."""
    if not app_settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured")

    briefing_prompt = await build_briefing(db)
    training_context = await build_training_context(db)
    system_prompt = build_system_prompt(training_context)

    client = anthropic.Anthropic(api_key=app_settings.anthropic_api_key)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": briefing_prompt}],
    )

    content = response.content[0].text if response.content else ""
    today = date.today()

    return BriefingOut(date=today.isoformat(), content=content)


@router.post("/chat")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    if not app_settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured")

    # Save user message
    user_msg = ChatMessage(
        conversation_id=request.conversation_id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)
    await db.commit()

    # Load conversation history
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == request.conversation_id)
        .order_by(ChatMessage.created_at)
    )
    all_messages = result.scalars().all()

    # Build messages for Claude (limit history)
    history = all_messages[-MAX_HISTORY_MESSAGES:]
    claude_messages = [{"role": m.role, "content": m.content} for m in history]

    # Build system prompt with training context
    training_context = await build_training_context(db)
    system_prompt = build_system_prompt(training_context)

    client = anthropic.Anthropic(api_key=app_settings.anthropic_api_key)

    async def generate():
        full_response = ""
        try:
            with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=system_prompt,
                messages=claude_messages,
            ) as stream:
                for text in stream.text_stream:
                    full_response += text
                    yield f"data: {json.dumps({'type': 'content_delta', 'text': text})}\n\n"

            # Save assistant message after streaming completes
            from app.database import async_session
            async with async_session() as save_db:
                assistant_msg = ChatMessage(
                    conversation_id=request.conversation_id,
                    role="assistant",
                    content=full_response,
                )
                save_db.add(assistant_msg)
                await save_db.commit()
                msg_id = assistant_msg.id

            yield f"data: {json.dumps({'type': 'message_complete', 'message_id': msg_id})}\n\n"

        except Exception as e:
            logger.error(f"Coach chat error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
