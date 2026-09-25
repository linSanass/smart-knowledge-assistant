"""
Function Calling 验证。

分三层：
1. 工具本身（calculator 白名单求值、current_time、knowledge_search）
2. 工具注册与错误处理
3. 端到端：真实调用 DeepSeek，验证 Tool Selection → Tool → Final Answer

直接运行：
    cd backend && python tests/test_tools.py
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

from services import tools


# =========================
# 1. calculator
# =========================

def check_calculator():

    cases = [
        ("1+1", 2),
        ("(1+2)*3", 9),
        ("10/4", 2.5),
        ("2**10", 1024),
        ("17 % 5", 2),
        ("17 // 5", 3),
        ("sqrt(16)", 4),
        ("round(3.14159, 2)", 3.14),
        ("max(1, 5, 3)", 5),
        ("abs(-7)", 7),
        ("pi", 3.141592653589793),
        ("-3 + 5", 2),
        ("2 * pi", 6.283185307179586)
    ]

    for expression, expected in cases:

        result = tools.calculator(expression)

        assert abs(result - expected) < 1e-9, (
            f"{expression} => {result}, 期望 {expected}"
        )

    print("[OK] calculator 正确计算", len(cases), "个表达式")

    # =========================
    # 必须拒绝危险输入
    # =========================

    dangerous = [
        "__import__('os').system('echo hi')",
        "open('/etc/passwd').read()",
        "1 if True else 2",
        "[x for x in range(3)]",
        "lambda: 1",
        "print(1)",
        "().__class__",
        "exec('1+1')",
        "1; 2",
        "a = 1"
    ]

    for expression in dangerous:

        try:

            tools.calculator(expression)

        except ValueError:

            continue

        raise AssertionError(
            f"危险表达式未被拒绝: {expression}"
        )

    print("[OK] calculator 拒绝", len(dangerous), "个非白名单表达式")

    # 超长与空输入
    for bad in ["", "   ", "1+" * 200]:

        try:

            tools.calculator(bad)

        except ValueError:

            continue

        raise AssertionError(f"非法输入未被拒绝: {bad[:20]}")

    print("[OK] calculator 拒绝空输入与超长表达式")


# =========================
# 2. current_time
# =========================

def check_current_time():

    result = tools.current_time("Asia/Shanghai")

    assert result["timezone"] == "Asia/Shanghai", result

    assert len(result["date"]) == 10, result

    assert len(result["time"]) == 8, result

    print("[OK] current_time:", result["datetime"], result["weekday"])

    # 非法时区名退回 UTC，而不是报错
    fallback = tools.current_time("Not/AZone")

    assert fallback["timezone"] == "UTC", fallback

    # 默认参数
    assert "datetime" in tools.current_time()

    print("[OK] current_time 非法时区退回 UTC")


# =========================
# 3. knowledge_search
# =========================

def check_knowledge_search():

    from services.rag_service import build_vector_store

    built = build_vector_store()

    assert built["chunk_count"] > 0, (
        "知识库为空，请确认 backend/uploads 下有 PDF"
    )

    result = tools.knowledge_search("HybridCLR", top_k=2)

    assert result["found"] is True, result

    assert len(result["results"]) == 2, result

    for item in result["results"]:

        assert item["filename"], item

        assert item["chunk"].strip(), item

    print(
        "[OK] knowledge_search 返回",
        len(result["results"]),
        "条，来源:",
        result["results"][0]["filename"]
    )

    # top_k 会被夹到合法范围
    assert len(
        tools.knowledge_search("Unity", top_k=999)["results"]
    ) <= 10

    print("[OK] knowledge_search top_k 被限制在合法范围")


# =========================
# 4. 注册表与错误处理
# =========================

def check_registry():

    names = {
        t["name"]
        for t in tools.list_tools()
    }

    assert names == {
        "calculator",
        "knowledge_search",
        "current_time"
    }, names

    print("[OK] 工具注册表:", sorted(names))

    # 参数是 JSON 字符串（DeepSeek 传过来的原始形态）
    outcome = tools.execute_tool(
        "calculator",
        '{"expression": "6*7"}'
    )

    assert outcome["ok"] is True, outcome

    assert outcome["content"] == "42", outcome

    print("[OK] execute_tool 解析 JSON 参数字符串")

    # 未知工具
    outcome = tools.execute_tool("nope", "{}")

    assert outcome["ok"] is False

    assert "未知工具" in outcome["content"]

    print("[OK] 未知工具返回错误而不是抛异常")

    # 参数错误
    outcome = tools.execute_tool("calculator", "{}")

    assert outcome["ok"] is False, outcome

    print("[OK] 缺少参数返回错误:", outcome["content"][:40])

    # 计算失败
    outcome = tools.execute_tool(
        "calculator",
        '{"expression": "1/0"}'
    )

    assert outcome["ok"] is False, outcome

    assert "ZeroDivisionError" in outcome["content"], outcome

    print("[OK] 计算异常被捕获:", outcome["content"][:40])


# =========================
# 5. 端到端
# =========================

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

    check_calculator()

    check_current_time()

    check_knowledge_search()

    check_registry()

    from main import app

    client = TestClient(app)

    check_endpoint(client)

    check_conversation_mode(client)

    print("\n全部测试通过")


if __name__ == "__main__":

    main()
