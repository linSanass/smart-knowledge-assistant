"""
Function Calling 服务。

流程：
    User
      ↓
    LLM（带 tools）
      ↓
    选择 Tool
      ↓
    执行 Tool
      ↓
    返回 Tool Result
      ↓
    LLM
      ↓
    Final Answer
"""

import json

from openai import OpenAI

from dotenv import load_dotenv

import os

from services import tools


load_dotenv()


client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


MODEL = "deepseek-chat"

# 单次请求里最多执行多少次工具调用，防止死循环
MAX_ITERATIONS = 3


SYSTEM_PROMPT = """你是一名可以使用工具的 AI 助手。

规则：
1. 需要计算时使用 calculator，不要自己心算。
2. 问题涉及用户上传的 PDF 知识库时，使用 knowledge_search。
3. 需要当前时间时，使用 current_time。
4. 如果工具返回了结果，请基于工具结果回答，不要编造。
5. 如果知识库中没有找到相关信息，请明确说明。
6. 不需要工具时直接回答。"""


def run_tools(
    message,
    role_prompt=None,
    history=None,
    max_iterations=MAX_ITERATIONS
):
    """
    带工具的多轮调用。

    返回:
        {
            "answer": 最终回答,
            "tool_calls": [ {name, arguments, result, ok}, ... ]
        }
    """

    system_prompt = SYSTEM_PROMPT

    if role_prompt:

        system_prompt = system_prompt + "\n\n" + role_prompt

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    for item in (history or []):

        if not item.get("content"):
            continue

        messages.append({
            "role": item["role"],
            "content": item["content"]
        })

    messages.append({
        "role": "user",
        "content": message
    })

    executed = []

    for _ in range(max_iterations):

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools.get_tool_schemas(),
            tool_choice="auto"
        )

        choice = response.choices[0].message

        tool_calls = choice.tool_calls or []

        # 没有工具调用，说明已经是最终回答
        if not tool_calls:

            return {
                "answer": choice.content or "",
                "tool_calls": executed
            }

        # 把模型这一轮的决策写回上下文
        messages.append({
            "role": "assistant",
            "content": choice.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments
                    }
                }
                for call in tool_calls
            ]
        })

        # 逐个执行工具
        for call in tool_calls:

            name = call.function.name

            outcome = tools.execute_tool(
                name,
                call.function.arguments
            )

            executed.append({
                "name": name,
                "arguments": parse_arguments(
                    call.function.arguments
                ),
                "result": outcome["content"],
                "ok": outcome["ok"]
            })

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": outcome["content"]
            })

    # 迭代次数用尽，让模型基于已有工具结果收尾
    final = client.chat.completions.create(
        model=MODEL,
        messages=messages + [{
            "role": "user",
            "content": "请直接根据以上工具结果给出最终回答。"
        }]
    )

    return {
        "answer": final.choices[0].message.content or "",
        "tool_calls": executed
    }


def parse_arguments(arguments):

    if isinstance(arguments, dict):

        return arguments

    try:

        return json.loads(arguments or "{}")

    except json.JSONDecodeError:

        return {"_raw": arguments}
