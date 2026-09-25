from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from pydantic import BaseModel

from sqlalchemy.orm import Session

from database import get_db

from services import conversation_service as conv


router = APIRouter(
    prefix="/conversations",
    tags=["conversations"]
)


# =========================
# 请求结构
# =========================

class ConversationCreate(BaseModel):

    title: str | None = None


class MessageCreate(BaseModel):

    message: str

    # chat / rag / tools
    mode: str = conv.MODE_CHAT

    # 仅 chat 模式使用；未知取值会退回 general
    role: str = "general"


# =========================
# 新建会话
# =========================

@router.post("")
def create_conversation(
    req: ConversationCreate | None = None,
    db: Session = Depends(get_db)
):

    conversation = conv.create_conversation(
        db,
        req.title if req else None
    )

    return conv.serialize_conversation(
        conversation
    )


# =========================
# 会话列表
# =========================

@router.get("")
def list_conversations(
    db: Session = Depends(get_db)
):

    return [
        conv.serialize_conversation(c)
        for c in conv.list_conversations(db)
    ]


# =========================
# 单个会话（含历史消息）
# =========================

@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db)
):

    conversation = conv.get_conversation(
        db,
        conversation_id
    )

    if conversation is None:

        raise HTTPException(
            status_code=404,
            detail="会话不存在"
        )

    return conv.serialize_conversation(
        conversation,
        with_messages=True
    )


# =========================
# 删除会话
# =========================

@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db)
):

    if not conv.delete_conversation(
        db,
        conversation_id
    ):

        raise HTTPException(
            status_code=404,
            detail="会话不存在"
        )

    return {
        "message": "会话已删除",
        "id": conversation_id
    }


# =========================
# 发送消息
# =========================

@router.post("/{conversation_id}/messages")
def send_message(
    conversation_id: int,
    req: MessageCreate,
    db: Session = Depends(get_db)
):

    if not req.message.strip():

        raise HTTPException(
            status_code=400,
            detail="消息不能为空"
        )

    if req.mode not in conv.MODES:

        raise HTTPException(
            status_code=400,
            detail=(
                "mode 只能是 "
                + " / ".join(conv.MODES)
            )
        )

    conversation = conv.get_conversation(
        db,
        conversation_id
    )

    if conversation is None:

        raise HTTPException(
            status_code=404,
            detail="会话不存在"
        )

    return conv.send_message(
        db,
        conversation,
        req.message,
        mode=req.mode,
        role=req.role
    )
