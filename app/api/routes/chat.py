from fastapi import APIRouter, Depends

from app.api.dependencies import get_chat_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest,
service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    reply= await service.reply(request.message)
    return ChatResponse(reply=reply)