from datetime import (
    datetime,
    timezone
)

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text
)

from sqlalchemy.orm import relationship

from database import Base


def utcnow():

    # 统一存 naive UTC，避免不同数据库对时区的处理差异
    return datetime.now(
        timezone.utc
    ).replace(tzinfo=None)


# =========================
# 知识库文档
# =========================

class Document(Base):

    __tablename__ = "documents"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # 用户上传时的原始文件名
    filename = Column(
        String(255),
        nullable=False,
        index=True
    )

    # 磁盘上的保存路径
    file_path = Column(
        String(512),
        nullable=False
    )

    # 解析出的文本块数量
    chunk_count = Column(
        Integer,
        default=0
    )

    # pending / processing / ready / failed
    status = Column(
        String(32),
        default="pending",
        index=True
    )

    # 解析失败时的原因
    error = Column(Text)

    # pdf / note
    #
    # 笔记与 PDF 存在同一张表里，好处是来源追踪、状态流转、
    # 索引失效这几条链完全复用，不用为笔记再写一套。
    #
    # server_default 是必须的：轻量迁移用 CreateColumn 生成 DDL，
    # 它只会带上 server_default。若只用 Python 侧的 default，
    # 生成的会是不带默认值的 NOT NULL 列，存量行会被填成空串而不是 'pdf'
    kind = Column(
        String(16),
        default="pdf",
        server_default="pdf",
        nullable=False
    )

    # 笔记正文；PDF 行为空。
    # 笔记的标题存在 filename 里，好让下游（chunks_store / 来源追踪）
    # 继续用同一个字段作展示名，不必到处分支
    content = Column(Text)

    created_at = Column(
        DateTime,
        default=utcnow
    )


# =========================
# 会话
# =========================

class Conversation(Base):

    __tablename__ = "conversations"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    title = Column(
        String(255),
        default="新会话"
    )

    created_at = Column(
        DateTime,
        default=utcnow
    )

    updated_at = Column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        index=True
    )

    messages = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.id"
    )


# =========================
# 聊天消息
# =========================

class ChatMessage(Base):

    __tablename__ = "chat_messages"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    conversation_id = Column(
        Integer,
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    # user / assistant
    role = Column(
        String(32),
        nullable=False
    )

    content = Column(Text)

    # RAG 引用来源，JSON 字符串
    sources = Column(Text)

    # Function Calling 轨迹，JSON 字符串
    tool_calls = Column(Text)

    created_at = Column(
        DateTime,
        default=utcnow
    )

    conversation = relationship(
        "Conversation",
        back_populates="messages"
    )
