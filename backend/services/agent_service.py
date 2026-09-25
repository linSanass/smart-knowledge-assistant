"""
Agent 服务。

和 Function Calling 走同一个循环，区别在于：
    - system prompt 要求分步思考，不急着给答案
    - 允许更多轮，支持「先查资料、再计算、再总结」这类多步任务

不引入 Agent Framework，保持可读可调试。
"""

from services import function_calling_service as fc


# 最多允许的步骤数，防止无限循环
MAX_STEPS = 6


AGENT_SYSTEM_PROMPT = """你是一个会分步使用工具的 Agent。

工作方式：
1. 先判断用户的问题需要哪些信息、需要调用哪些工具。
2. 一次只做一件确定的事；需要多个工具时，按顺序逐步调用。
3. 每次拿到工具结果后，先判断是否已经足够回答，不够就继续调用下一个工具。
4. 信息足够时，用中文给出最终答案，并说明依据。

可用工具：
- calculator：数学计算，不要自己心算
- knowledge_search：检索用户上传的 PDF 知识库
- current_time：获取当前日期时间

约束：
- 不要编造工具没有返回的信息。
- 知识库里没有的内容，明确说明「知识库中没有找到相关信息」。
- 最终答案要简洁、准确。"""


def run_agent(
    message,
    history=None,
    role_prompt=None
):
    """
    执行一次 Agent 任务。

    返回:
        {
            "answer": 最终回答,
            "tool_calls": [ {step, name, arguments, result, ok}, ... ],
            "iterations": 轮数,
            "steps": 工具调用次数
        }
    """

    system_prompt = AGENT_SYSTEM_PROMPT

    if role_prompt:

        system_prompt = system_prompt + "\n\n" + role_prompt

    result = fc.run_tool_loop(
        message,
        system_prompt=system_prompt,
        history=history,
        max_iterations=MAX_STEPS
    )

    result["steps"] = len(
        result.get("tool_calls", [])
    )

    return result
