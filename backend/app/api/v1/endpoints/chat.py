from typing import Any, List, Optional
from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.session import get_db
from app.api import deps
from app.schemas import chat_schema
from app.models.chat import ChatSession, ChatMessage
from app.models.user import User
from app.services.chat_engine import ChatEngine
import uuid

router = APIRouter()

@router.post("/completion", response_model=chat_schema.ChatResponse)
async def chat_completion(
    *,
    db: AsyncSession = Depends(get_db),
    chat_request: chat_schema.ChatRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Chat completion endpoint with session support.
    """
    chat_engine = ChatEngine()
    
    # 1. Manage Session
    session_id = chat_request.session_id
    if not session_id:
        # Create new session
        session_id = str(uuid.uuid4())
        new_session = ChatSession(
            id=session_id,
            user_id=current_user.id,
            title=chat_request.query[:50] + "..." if len(chat_request.query) > 50 else chat_request.query
        )
        db.add(new_session)
        # We don't commit yet, wait for success
    else:
        # Verify session ownership
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id))
        session = result.scalars().first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        # Update timestamp
        session.updated_at = datetime.utcnow() # Import datetime? No, sqlalchemy handles default? No, onupdate. But manual update implies touch.
        # Actually onupdate handles it if we commit.
    
    # 2. Save User Message
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=chat_request.query
    )
    db.add(user_msg)
    await db.commit() # Commit user message immediately
    
    # 3. Get History for context
    # Fetch last N messages
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    history_msgs = history_result.scalars().all()
    history_strings = [msg.content for msg in history_msgs] # Simplified. Ideally should be Role: Content
    
    # 4. Generate Response
    try:
        response_text = await chat_engine.chat(
            user_query=chat_request.query,
            history=history_strings, 
            user_info=current_user
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat Error: {str(e)}")
    
    # 5. Save AI Response
    # Re-fetch session to ensure it's attached if needed, or just add new message
    ai_msg = ChatMessage(
        session_id=session_id,
        role="ai",
        content=response_text
    )
    db.add(ai_msg)
    
    await db.commit()
    
    return chat_schema.ChatResponse(answer=response_text, session_id=session_id)

@router.get("/sessions", response_model=List[chat_schema.ChatSession])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List chat sessions for the current user.
    """
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(desc(ChatSession.is_pinned), desc(ChatSession.updated_at))
        .offset(skip)
        .limit(limit)
    )
    sessions = result.scalars().all()
    return sessions

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Delete a chat session.
    """
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await db.delete(session) # Cascade should handle messages
    await db.commit()
    return

@router.patch("/sessions/{session_id}", response_model=chat_schema.ChatSession)
async def update_session(
    session_id: str,
    session_in: chat_schema.ChatSessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update a chat session (rename, pin).
    """
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_in.title is not None:
        session.title = session_in.title
    if session_in.is_pinned is not None:
        session.is_pinned = session_in.is_pinned
        
    await db.commit()
    await db.refresh(session)
    return session

@router.get("/sessions/{session_id}/messages", response_model=List[chat_schema.ChatMessage])
async def list_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get messages for a specific session.
    """
    # Verify access
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    return messages
