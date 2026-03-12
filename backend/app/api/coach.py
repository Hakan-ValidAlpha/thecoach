import json
import logging
from datetime import date, datetime, timezone

import anthropic
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.database import get_db
from app.models.chat import ChatMessage
from app.models.briefing import DailyBriefing
from app.models.settings import Settings as DBSettings
from app.schemas.coach import (
    ChatRequest, ChatMessageOut, ConversationSummary,
    BriefingOut, BriefingChange,
)
from app.services.coach_context import build_training_context, build_system_prompt

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_HISTORY_MESSAGES = 20


async def _get_anthropic_key(db: AsyncSession) -> str:
    db_settings = await db.get(DBSettings, 1)
    key = (db_settings.anthropic_api_key if db_settings else None) or app_settings.anthropic_api_key
    return key or ""


# --- Conversations ---

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
    return [
        ConversationSummary(
            conversation_id=row.conversation_id,
            title=(row.first_msg or "New conversation")[:60],
            last_message_at=row.last_at,
            message_count=row.msg_count,
        )
        for row in result.all()
    ]


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
    for m in result.scalars().all():
        await db.delete(m)
    await db.commit()
    return {"status": "deleted"}


# --- Briefing ---

@router.get("/briefing", response_model=BriefingOut)
async def get_briefing(db: AsyncSession = Depends(get_db)):
    """Get today's stored briefing if it exists."""
    today = date.today()

    result = await db.execute(
        select(DailyBriefing).where(DailyBriefing.date == today)
    )
    stored = result.scalar_one_or_none()

    if stored and stored.status == "completed":
        changes = None
        if stored.changes_made:
            changes = [BriefingChange(**c) for c in stored.changes_made]
        return BriefingOut(
            date=today.isoformat(),
            content=stored.content,
            changes_made=changes,
            generated_at=stored.created_at.isoformat() if stored.created_at else None,
            status="completed",
        )

    if stored and stored.status == "pending":
        return BriefingOut(
            date=today.isoformat(),
            content="Your briefing is being generated...",
            status="pending",
        )

    # No briefing yet — return empty so frontend can show generate button
    return BriefingOut(
        date=today.isoformat(),
        content="",
        status="none",
    )


@router.post("/briefing/generate")
async def trigger_briefing(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Manually trigger the full briefing pipeline (sync + AI + tool use)."""
    today = date.today()

    # Mark as pending
    result = await db.execute(
        select(DailyBriefing).where(DailyBriefing.date == today)
    )
    existing = result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.commit()

    from app.services.daily_briefing import run_daily_briefing_pipeline
    background_tasks.add_task(run_daily_briefing_pipeline)
    return {"status": "generating"}


@router.get("/briefings", response_model=list[BriefingOut])
async def list_briefings(limit: int = 7, db: AsyncSession = Depends(get_db)):
    """Get recent briefings."""
    result = await db.execute(
        select(DailyBriefing)
        .where(DailyBriefing.status == "completed")
        .order_by(DailyBriefing.date.desc())
        .limit(limit)
    )
    briefings = []
    for b in result.scalars().all():
        changes = [BriefingChange(**c) for c in b.changes_made] if b.changes_made else None
        briefings.append(BriefingOut(
            date=b.date.isoformat(),
            content=b.content,
            changes_made=changes,
            generated_at=b.created_at.isoformat() if b.created_at else None,
            status=b.status,
        ))
    return briefings


# --- Chat ---

@router.post("/chat")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    api_key = await _get_anthropic_key(db)
    if not api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not configured. Set it in Settings.")

    user_msg = ChatMessage(
        conversation_id=request.conversation_id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)
    await db.commit()

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == request.conversation_id)
        .order_by(ChatMessage.created_at)
    )
    all_messages = result.scalars().all()

    history = all_messages[-MAX_HISTORY_MESSAGES:]
    claude_messages = [{"role": m.role, "content": m.content} for m in history]

    training_context = await build_training_context(db)
    system_prompt = build_system_prompt(training_context)

    # Add tool-use instruction to system prompt for chat
    chat_system = system_prompt + """

You have tools available to modify the training plan. \
You can create, move, skip, or delete workouts. When you use a tool, explain what you did naturally in your response.

WHEN TO USE TOOLS:
- When the user explicitly asks for a change (e.g., "add a run tomorrow", "skip today's workout")
- When the user tells you how they feel and it should affect their training (e.g., "I'm exhausted" → suggest skipping or replacing a hard workout)
- When recommending a workout as part of your coaching advice — create it directly so they don't have to do it manually
- Always explain WHY you're making the change, referencing their data or what they told you"""

    client = anthropic.Anthropic(api_key=api_key)

    from app.services.daily_briefing import COACH_TOOLS, TOOL_EXECUTORS

    # Get Garmin client for syncing tool actions
    garmin_client = None
    db_settings = await db.get(DBSettings, 1)
    garmin_email = (db_settings.garmin_email if db_settings else None) or app_settings.garmin_email
    garmin_password = (db_settings.garmin_password if db_settings else None) or app_settings.garmin_password
    if garmin_email and garmin_password:
        try:
            import asyncio
            from app.services.garmin_sync import _get_garmin_client
            garmin_client = await asyncio.to_thread(_get_garmin_client, garmin_email, garmin_password)
        except Exception as e:
            logger.warning(f"Could not get Garmin client for chat tools: {e}")

    async def generate():
        full_response = ""
        changes = []
        messages = list(claude_messages)
        max_iterations = 5

        try:
            for iteration in range(max_iterations):
                # First iteration: stream the response for fast UX
                # Subsequent iterations (after tool use): also stream
                tool_use_blocks = []
                text_in_turn = ""

                with client.messages.stream(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2048,
                    system=chat_system,
                    tools=COACH_TOOLS,
                    messages=messages,
                ) as stream:
                    for event in stream:
                        if hasattr(event, 'type'):
                            if event.type == 'content_block_delta':
                                if hasattr(event.delta, 'text'):
                                    full_response += event.delta.text
                                    text_in_turn += event.delta.text
                                    yield f"data: {json.dumps({'type': 'content_delta', 'text': event.delta.text})}\n\n"

                    # Get the final message to check for tool use
                    final_message = stream.get_final_message()

                if final_message.stop_reason != "tool_use":
                    break

                # Handle tool use
                tool_results = []
                for block in final_message.content:
                    if block.type == "tool_use":
                        tool_use_blocks.append(block)
                        executor = TOOL_EXECUTORS.get(block.name)
                        if executor:
                            from app.database import async_session
                            async with async_session() as tool_db:
                                result = await executor(tool_db, block.input, garmin_client)
                                await tool_db.commit()

                            change_info = {
                                "tool": block.name,
                                "reason": block.input.get("reason", ""),
                                "result": result,
                            }
                            changes.append(change_info)

                            # Notify frontend about the action
                            yield f"data: {json.dumps({'type': 'tool_action', 'tool': block.name, 'reason': block.input.get('reason', ''), 'result': result})}\n\n"

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result),
                            })
                        else:
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps({"error": f"Unknown tool: {block.name}"}),
                                "is_error": True,
                            })

                # Continue the conversation with tool results
                messages.append({"role": "assistant", "content": final_message.content})
                messages.append({"role": "user", "content": tool_results})

            # Save the full response
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

            result_data = {'type': 'message_complete', 'message_id': msg_id}
            if changes:
                result_data['changes'] = changes
            yield f"data: {json.dumps(result_data)}\n\n"

        except Exception as e:
            logger.error(f"Coach chat error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
