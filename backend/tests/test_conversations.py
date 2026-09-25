"""
Conversation API 验证。

会真实调用 DeepSeek，所以需要 backend/.env 里配置有效的 DEEPSEEK_API_KEY。

直接运行：
    cd backend && python tests/test_conversations.py
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

from fastapi.testclient import TestClient

from main import app


def main():

    client = TestClient(app)

    # =========================
    # 1. 新建会话
    # =========================

    resp = client.post(
        "/conversations",
        json={}
    )

    assert resp.status_code == 200, resp.text

    conversation = resp.json()

    conversation_id = conversation["id"]

    assert conversation["title"] == "新会话"
    assert conversation["message_count"] == 0

    print("[OK] 新建会话 id =", conversation_id)

    # =========================
    # 2. 会话列表包含它
    # =========================

    resp = client.get("/conversations")

    assert resp.status_code == 200

    ids = [
        c["id"]
        for c in resp.json()
    ]

    assert conversation_id in ids

    print("[OK] 会话列表返回", len(ids), "条")

    # =========================
    # 3. chat 模式发送消息
    # =========================

    resp = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "message": "用一句话介绍 HybridCLR",
            "mode": "chat",
            "role": "unity"
        }
    )

    assert resp.status_code == 200, resp.text

    data = resp.json()

    assert data["answer"].strip()

    assert data["user_message"]["role"] == "user"

    assert (
        data["assistant_message"]["role"]
        == "assistant"
    )

    # 标题应该由首条消息生成
    assert data["title"] != "新会话", data["title"]

    print("[OK] chat 模式回答:", data["answer"][:40])

    print("[OK] 自动标题:", data["title"])

    # =========================
    # 4. 历史消息落库
    # =========================

    resp = client.get(
        f"/conversations/{conversation_id}"
    )

    assert resp.status_code == 200

    detail = resp.json()

    assert len(detail["messages"]) == 2

    assert detail["messages"][0]["role"] == "user"

    assert (
        detail["messages"][1]["role"]
        == "assistant"
    )

    print("[OK] 历史消息数 =", len(detail["messages"]))

    # =========================
    # 5. rag 模式发送消息
    # =========================

    # FAISS 索引是进程内内存态，测试进程需要先构建
    resp = client.get("/build-rag")

    assert resp.status_code == 200

    assert resp.json()["chunk_count"] > 0, (
        "知识库为空，请先确认 backend/uploads 下有 PDF"
    )

    resp = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "message": "HybridCLR 是什么?",
            "mode": "rag"
        }
    )

    assert resp.status_code == 200, resp.text

    rag_data = resp.json()

    assert rag_data["answer"].strip()

    assert isinstance(rag_data["sources"], list)

    assert len(rag_data["sources"]) > 0, "RAG 未返回来源"

    print(
        "[OK] rag 模式来源数 =",
        len(rag_data["sources"])
    )

    # =========================
    # 6. 两轮对话共 4 条消息
    # =========================

    resp = client.get(
        f"/conversations/{conversation_id}"
    )

    assert len(resp.json()["messages"]) == 4

    print("[OK] 两轮对话共 4 条消息")

    # =========================
    # 7. 多轮上下文生效
    # =========================

    resp = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "message": "我刚才第一个问题问的是什么?",
            "mode": "chat",
            "role": "unity"
        }
    )

    assert resp.status_code == 200

    context_answer = resp.json()["answer"]

    assert "HybridCLR" in context_answer, (
        "多轮上下文未生效: " + context_answer
    )

    print("[OK] 多轮上下文生效")

    # =========================
    # 8. 参数校验
    # =========================

    resp = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "message": "hi",
            "mode": "unknown"
        }
    )

    assert resp.status_code == 400

    resp = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "message": "   ",
            "mode": "chat"
        }
    )

    assert resp.status_code == 400

    resp = client.post(
        "/conversations/999999999/messages",
        json={
            "message": "hi",
            "mode": "chat"
        }
    )

    assert resp.status_code == 404

    resp = client.get("/conversations/999999999")

    assert resp.status_code == 404

    print("[OK] 400 / 404 校验正常")

    # =========================
    # 9. 删除会话（级联删消息）
    # =========================

    resp = client.delete(
        f"/conversations/{conversation_id}"
    )

    assert resp.status_code == 200

    resp = client.get(
        f"/conversations/{conversation_id}"
    )

    assert resp.status_code == 404

    resp = client.delete(
        f"/conversations/{conversation_id}"
    )

    assert resp.status_code == 404

    print("[OK] 删除会话正常")

    print("\n全部测试通过")


if __name__ == "__main__":

    main()
