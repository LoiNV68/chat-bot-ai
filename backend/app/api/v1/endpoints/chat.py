from typing import Any
from fastapi import APIRouter, Depends
from app.api import deps
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.services.chat_engine import ChatEngine
from app.models.user import User

router = APIRouter()

@router.post("/completion", response_model=ChatResponse)
async def chat_completion(
    *,
    chat_request: ChatRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    chat_engine = ChatEngine()
    response_text = await chat_engine.chat(
        user_query=chat_request.query,
        history=chat_request.history,
        user_info=current_user
    )
    
    # We might want to return sources too, but ChatEngine needs to return them.
    # For now returns just answer in ChatResponse. 
    # ChatEngine.chat returns str currently.
    
    return ChatResponse(answer=response_text)
