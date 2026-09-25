"""
Function Calling 端到端验证（**真实调用 DeepSeek**）。

覆盖：
1. POST /tools/chat：模型真的选中了正确的工具，并用工具结果回答
2. 会话 tools 模式：工具轨迹能写入 chat_messages 并原样读回

工具本身的单元测试在 tests/test_tools.py，那个文件不调用 DeepSeek，
所以 CI 跑它而不跑这个。

需要 DEEPSEEK_API_KEY、MySQL，以及 backend/uploads 下已建索引的 PDF。

直接运行：
    cd backend && python tests/test_tools_endpoint.py
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


def check_endpoint(client):

    resp = client.get("/tools")

    assert resp.status_code == 200

    assert len(resp.json()["tools"]) == 3

    # =========================
    # 应该走 calculator
    # =========================

    resp = client.post(
        "/tools/chat",
        json={"message": "帮我算一下 (123 + 456) * 7 等于多少"}
    )

    assert resp.status_code == 200, resp.text

    data = resp.json()

    names = [c["name"] for c in data["tool_calls"]]

    assert "calculator" in names, (
        "未选择 calculator: " + str(data)
    )

    assert "4053" in data["answer"], data["answer"]

    print(
        "[OK] calculator 端到端:",
        names,
        "=>",
        data["answer"][:40]
    )

    # =========================
    # 应该走 current_time
    # =========================

    resp = client.post(
        "/tools/chat",
        json={"message": "现在几点了？"}
    )

    data = resp.json()

    names = [c["name"] for c in data["tool_calls"]]

    assert "current_time" in names, (
        "未选择 current_time: " + str(data)
    )

    print("[OK] current_time 端到端:", data["answer"][:40])

    # =========================
    # 应该走 knowledge_search
    # =========================

    resp = client.post(
        "/tools/chat",
        json={
            "message": "根据知识库，HybridCLR 是什么？"
        }
    )

    data = resp.json()

    names = [c["name"] for c in data["tool_calls"]]

    assert "knowledge_search" in names, (
        "未选择 knowledge_search: " + str(data)
    )

    assert data["answer"].strip()

    print("[OK] knowledge_search 端到端:", data["answer"][:50])

    # =========================
    # 参数校验
    # =========================

    resp = client.post(
        "/tools/chat",
        json={"message": "   "}
    )

    assert resp.status_code == 400

    print("[OK] 空消息返回 400")


def check_conversation_mode(client):

    conversation = client.post(
        "/conversations",
        json={}
    ).json()

    conversation_id = conversation["id"]

    try:

        resp = client.post(
            f"/conversations/{conversation_id}/messages",
            json={
                "message": "算一下 88 * 3",
                "mode": "tools"
            }
        )

        assert resp.status_code == 200, resp.text

        data = resp.json()

        assert data["tool_calls"], "会话未返回工具轨迹"

        assert "264" in data["answer"], data["answer"]

        # 轨迹要能持久化
        detail = client.get(
            f"/conversations/{conversation_id}"
        ).json()

        assistant = [
            m for m in detail["messages"]
            if m["role"] == "assistant"
        ][0]

        assert assistant["tool_calls"] == data["tool_calls"], (
            "工具轨迹未正确持久化"
        )

        print(
            "[OK] 会话 tools 模式可持久化轨迹:",
            [c["name"] for c in data["tool_calls"]]
        )

    finally:

        client.delete(f"/conversations/{conversation_id}")


def main():

    # knowledge_search 端到端需要索引已构建
    from helpers import ensure_index

    from main import app

    client = TestClient(app)

    ensure_index(client)

    check_endpoint(client)

    check_conversation_mode(client)

    print("\n全部测试通过")


if __name__ == "__main__":

    main()
