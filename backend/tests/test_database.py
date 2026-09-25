"""
MySQL 持久化层验证。

直接运行：
    cd backend && python tests/test_database.py
"""

import os
import sys

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from sqlalchemy import inspect, text

from database import (
    Base,
    SessionLocal,
    engine,
    init_db
)

from models import (
    ChatMessage,
    Conversation,
    Document
)


def main():

    init_db()

    # =========================
    # 1. 表是否存在
    # =========================

    tables = set(
        inspect(engine).get_table_names()
    )

    for name in [
        "documents",
        "conversations",
        "chat_messages"
    ]:

        assert name in tables, f"缺少表 {name}"

    print("[OK] 三张表创建成功:", sorted(tables))

    # =========================
    # 2. 写入 + 读取
    # =========================

    db = SessionLocal()

    try:

        doc = Document(
            filename="test.pdf",
            file_path="uploads/test.pdf",
            chunk_count=3,
            status="ready"
        )

        conv = Conversation(
            title="测试会话"
        )

        db.add(doc)
        db.add(conv)
        db.flush()

        db.add(
            ChatMessage(
                conversation_id=conv.id,
                role="user",
                content="你好"
            )
        )

        db.add(
            ChatMessage(
                conversation_id=conv.id,
                role="assistant",
                content="你好，我是AI助手"
            )
        )

        db.commit()

        conv_id = conv.id
        doc_id = doc.id

        # 重新查一遍，确认真的落库了
        db.expire_all()

        loaded = db.get(
            Conversation,
            conv_id
        )

        assert loaded is not None
        assert len(loaded.messages) == 2

        assert (
            loaded.messages[0].content
            == "你好"
        )

        assert (
            loaded.messages[1].role
            == "assistant"
        )

        print(
            "[OK] 会话读写正常, messages =",
            len(loaded.messages)
        )

        # =========================
        # 3. 级联删除
        # =========================

        db.delete(loaded)

        db.commit()

        remain = db.get(
            Conversation,
            conv_id
        )

        assert remain is None

        orphan = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.conversation_id
                == conv_id
            )
            .count()
        )

        assert orphan == 0, "级联删除未生效"

        print("[OK] 级联删除正常")

        # =========================
        # 4. 清理测试文档
        # =========================

        db.delete(db.get(Document, doc_id))

        db.commit()

    finally:

        db.close()

    # =========================
    # 5. 确认真的是 MySQL
    # =========================

    with engine.connect() as conn:

        version = conn.execute(
            text("SELECT VERSION()")
        ).scalar()

    assert "MariaDB" not in version

    print("[OK] 数据库:", version)

    print("\n全部测试通过")


if __name__ == "__main__":

    main()
