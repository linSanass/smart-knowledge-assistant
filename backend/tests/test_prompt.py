"""
Prompt Engineering 验证。

分两部分：
1. 结构检查：Prompt 必须包含 System Instruction / Retrieved Context / User Question
2. 行为检查：真实调用 DeepSeek，验证「基于知识库回答」与「不知道就说不知道」

直接运行：
    cd backend && python tests/test_prompt.py
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

from helpers import ensure_index

from services import prompts


def check_structure():

    messages = prompts.build_rag_messages(
        context="[片段1] 来源: a.pdf (第1块)\n对象池可以复用对象。",
        question="什么是对象池?"
    )

    # 1. 两条消息：system + user
    assert len(messages) == 2, messages

    system = messages[0]
    user = messages[1]

    assert system["role"] == "system"

    assert user["role"] == "user"

    # 2. System Instruction
    for keyword in [
        "知识库",
        "不要编造",
        "知识库中没有找到相关信息"
    ]:

        assert keyword in system["content"], (
            f"System Prompt 缺少约束: {keyword}"
        )

    # 3. Retrieved Context
    assert "对象池可以复用对象" in user["content"], (
        "User Prompt 未包含检索上下文"
    )

    assert "知识库内容" in user["content"]

    # 4. User Question
    assert "什么是对象池?" in user["content"], (
        "User Prompt 未包含用户问题"
    )

    assert "用户问题" in user["content"]

    print("[OK] Prompt 结构包含 System / Context / Question")

    print("[OK] System Prompt 含「不编造」与「不知道就说不知道」约束")


def check_behavior():

    from main import app

    client = TestClient(app)

    # 构建已异步化：只保证索引可用，结果从 /documents/status 读
    ensure_index(client)

    # =========================
    # 1. 知识库内的问题：应该基于知识库回答
    # =========================

    resp = client.post(
        "/rag-chat",
        json={
            "question": "What is HybridCLR? Answer in one sentence."
        }
    )

    assert resp.status_code == 200, resp.text

    inside = resp.json()

    answer = inside["answer"]

    assert answer.strip()

    assert prompts.NO_CONTEXT_ANSWER not in answer, (
        "知识库内的问题被误判为无答案: " + answer
    )

    assert "HybridCLR" in answer, answer

    print("[OK] 知识库内问题有回答:", answer[:60])

    # =========================
    # 2. 知识库外的问题：必须明确说不知道，不能编造
    # =========================

    resp = client.post(
        "/rag-chat",
        json={
            "question": "法国的首都是哪里？请直接回答城市名。"
        }
    )

    assert resp.status_code == 200, resp.text

    outside = resp.json()["answer"]

    # 检索一定返回 top-k 片段，所以这里检验的是模型没有被无关上下文带跑
    assert "巴黎" not in outside, (
        "模型使用了知识库以外的知识: " + outside
    )

    assert prompts.NO_CONTEXT_ANSWER in outside, (
        "知识库外问题没有明确说明无答案: " + outside
    )

    print("[OK] 知识库外问题明确拒答:", outside[:60])

    # =========================
    # 3. 长度约束：不超过「一般 200 字」太多
    # =========================

    resp = client.post(
        "/rag-chat",
        json={"question": "What is Addressables?"}
    )

    length = len(resp.json()["answer"])

    assert length < 600, (
        f"回答过长 ({length} 字)，Prompt 长度约束未生效"
    )

    print("[OK] 回答长度合理:", length, "字")


def main():

    check_structure()

    check_behavior()

    print("\n全部测试通过")


if __name__ == "__main__":

    main()
