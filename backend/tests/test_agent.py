"""
Agent 验证。

重点：
1. Agent 可以选择 calculator / knowledge_search / current_time
2. 能完成需要多个工具的多步任务
3. 轨迹带 step 序号并可持久化

直接运行：
    cd backend && python tests/test_agent.py
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

from services import agent_service


MULTI_TOOL_QUESTION = (
    "请帮我做三件事："
    "1) 现在北京时间几点？"
    "2) 计算 23 * 47；"
    "3) 在知识库里查一下 HybridCLR 是什么。"
    "最后把三件事的结果汇总告诉我。"
)


def check_config():

    assert agent_service.MAX_STEPS >= 3, (
        "多步任务至少需要 3 步"
    )

    assert "知识库" in agent_service.AGENT_SYSTEM_PROMPT

    print(
        "[OK] Agent 配置: MAX_STEPS =",
        agent_service.MAX_STEPS
    )


def check_multi_step():

    result = agent_service.run_agent(
        MULTI_TOOL_QUESTION
    )

    calls = result["tool_calls"]

    names = [call["name"] for call in calls]

    assert calls, "Agent 没有调用任何工具"

    assert len(calls) >= 2, (
        f"多步任务只调用了 {len(calls)} 次工具: {names}"
    )

    assert len(set(names)) >= 2, (
        f"多步任务只用了同一类工具: {names}"
    )

    # step 必须是 1..n
    assert [c["step"] for c in calls] == list(
        range(1, len(calls) + 1)
    ), calls

    # calculator 必须算对
    calc = [
        c for c in calls
        if c["name"] == "calculator"
    ]

    if calc:

        assert "1081" in calc[0]["result"], calc[0]

    assert result["answer"].strip(), "Agent 没有给出最终答案"

    assert result["steps"] == len(calls)

    print("[OK] Agent 多步任务调用顺序:", names)

    print("[OK] 最终答案:", result["answer"][:80].replace("\n", " "))


def check_endpoints(client):

    resp = client.get("/agent/tools")

    assert resp.status_code == 200, resp.text

    data = resp.json()

    assert data["max_steps"] == agent_service.MAX_STEPS

    assert {
        t["name"] for t in data["tools"]
    } == {
        "calculator",
        "knowledge_search",
        "current_time"
    }

    print("[OK] /agent/tools 返回 3 个工具")

    resp = client.post(
        "/agent/chat",
        json={"message": "计算 (99 - 19) / 8"}
    )

    assert resp.status_code == 200, resp.text

    result = resp.json()

    names = [c["name"] for c in result["tool_calls"]]

    assert "calculator" in names, result

    assert "10" in result["answer"], result["answer"]

    print("[OK] /agent/chat 端到端:", names, "=>", result["answer"][:40])

    resp = client.post(
        "/agent/chat",
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
                "message": MULTI_TOOL_QUESTION,
                "mode": "agent"
            }
        )

        assert resp.status_code == 200, resp.text

        data = resp.json()

        assert len(data["tool_calls"]) >= 2, (
            "会话 agent 模式未完成多步任务"
        )

        detail = client.get(
            f"/conversations/{conversation_id}"
        ).json()

        assistant = [
            m for m in detail["messages"]
            if m["role"] == "assistant"
        ][0]

        assert (
            assistant["tool_calls"]
            == data["tool_calls"]
        ), "Agent 轨迹未正确持久化"

        print(
            "[OK] 会话 agent 模式轨迹可持久化:",
            [c["name"] for c in data["tool_calls"]]
        )

    finally:

        client.delete(f"/conversations/{conversation_id}")


def main():

    check_config()

    from main import app

    client = TestClient(app)

    resp = client.get("/build-rag")

    assert resp.status_code == 200

    assert resp.json()["chunk_count"] > 0, (
        "知识库为空，请确认 backend/uploads 下有 PDF"
    )

    check_multi_step()

    check_endpoints(client)

    check_conversation_mode(client)

    print("\n全部测试通过")


if __name__ == "__main__":

    main()
