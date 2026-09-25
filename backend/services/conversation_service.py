import json

from models import (
    ChatMessage,
    Conversation,
    utcnow
)

from services import chat_service

from services import function_calling_service

from services.rag_service import rag_chat


# =========================
# 会话模式
# =========================

MODE_CHAT = "chat"

MODE_RAG = "rag"

# Function Calling 模式
MODE_TOOLS = "tools"

MODES = (
    MODE_CHAT,
    MODE_RAG,
    MODE_TOOLS
)

# 送给 LLM 的历史消息条数上限
HISTORY_LIMIT = 20

# 会话标题长度上限
TITLE_LIMIT = 30


# =========================
# 序列化
# =========================

def serialize_message(message):

    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,

        # sources 在库里是 JSON 字符串
        "sources": (
            json.loads(message.sources)
            if message.sources
            else []
        ),

        "tool_calls": (
            json.loads(message.tool_calls)
            if message.tool_calls
            else []
        ),

        "created_at": (
            message.created_at.isoformat()
            if message.created_at
            else None
        )
    }


def serialize_conversation(
    conversation,
    with_messages=False
):

    data = {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": (
            conversation.created_at.isoformat()
            if conversation.created_at
            else None
        ),
        "updated_at": (
            conversation.updated_at.isoformat()
            if conversation.updated_at
            else None
        ),
        "message_count": len(conversation.messages)
    }

    if with_messages:

        data["messages"] = [
            serialize_message(m)
            for m in conversation.messages
        ]

    return data


# =========================
# 增
# =========================

def create_conversation(
    db,
    title=None
):

    conversation = Conversation(
        title=title or "新会话"
    )

    db.add(conversation)

    db.commit()

    db.refresh(conversation)

    return conversation


def add_message(
    db,
    conversation_id,
    role,
    content,
    sources=None,
    tool_calls=None
):

    message = ChatMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,

        # 统一存 JSON 字符串
        sources=(
            json.dumps(sources, ensure_ascii=False)
            if sources
            else None
        ),

        tool_calls=(
            json.dumps(tool_calls, ensure_ascii=False)
            if tool_calls
            else None
        )
    )

    db.add(message)

    db.commit()

    db.refresh(message)

    return message


# =========================
# 查
# =========================

def list_conversations(db):

    return (
        db.query(Conversation)
        .order_by(
            Conversation.updated_at.desc(),
            Conversation.id.desc()
        )
        .all()
    )


def get_conversation(
    db,
    conversation_id
):

    return db.get(
        Conversation,
        conversation_id
    )


def get_history(
    db,
    conversation_id,
    limit=HISTORY_LIMIT
):

    rows = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.conversation_id
            == conversation_id
        )
        .order_by(
            ChatMessage.id.desc()
        )
        .limit(limit)
        .all()
    )

    # 倒序取最近 N 条后再还原成时间正序
    rows.reverse()

    return [
        {
            "role": row.role,
            "content": row.content
        }
        for row in rows
    ]


# =========================
# 删
# =========================

def delete_conversation(
    db,
    conversation_id
):

    conversation = get_conversation(
        db,
        conversation_id
    )

    if conversation is None:

        return False

    # relationship 配置了 cascade，消息会一起删除
    db.delete(conversation)

    db.commit()

    return True


# =========================
# 标题
# =========================

def build_title(text):

    title = " ".join(
        (text or "").split()
    )

    if not title:

        return "新会话"

    if len(title) <= TITLE_LIMIT:

        return title

    return title[:TITLE_LIMIT] + "..."


# =========================
# 一轮对话
# =========================

def send_message(
    db,
    conversation,
    message,
    mode=MODE_CHAT,
    role="unity"
):
    """
    完整流程：

    User Message
      ↓
    MySQL
      ↓
    LLM / RAG
      ↓
    Assistant Message
      ↓
    MySQL
    """

    # 1. 先取出本轮之前的历史，作为 LLM 上下文
    #    必须在写入当前提问前取，否则当前提问会重复出现
    history = get_history(
        db,
        conversation.id
    )

    # 2. 落库用户消息
    user_message = add_message(
        db,
        conversation.id,
        "user",
        message
    )

    # 第一条消息用来生成会话标题
    if conversation.title in (None, "", "新会话"):

        conversation.title = build_title(
            message
        )

    # 3. 调用 LLM / RAG / Function Calling
    sources = []

    tool_calls = []

    if mode == MODE_RAG:

        result = rag_chat(message)

        answer = result.get(
            "answer",
            ""
        )

        sources = result.get(
            "sources",
            []
        )

    elif mode == MODE_TOOLS:

        result = function_calling_service.run_tools(
            message,
            role_prompt=chat_service.roles.get(role),
            history=history
        )

        answer = result.get(
            "answer",
            ""
        )

        tool_calls = result.get(
            "tool_calls",
            []
        )

    else:

        answer = chat_service.chat_with_history(
            message,
            role,
            history
        )

    # 4. 再落库助手消息
    assistant_message = add_message(
        db,
        conversation.id,
        "assistant",
        answer,
        sources,
        tool_calls
    )

    # 5. 显式刷新时间，让它排到会话列表最前
    #    只改 title 时不会触发 onupdate，所以这里手动赋值
    conversation.updated_at = utcnow()

    db.commit()

    db.refresh(conversation)

    return {
        "conversation_id": conversation.id,
        "title": conversation.title,
        "answer": answer,
        "sources": sources,
        "tool_calls": tool_calls,
        "user_message": serialize_message(
            user_message
        ),
        "assistant_message": serialize_message(
            assistant_message
        )
    }
