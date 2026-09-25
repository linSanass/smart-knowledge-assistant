from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

roles = {

    "general":
    """
    你是一名通用AI助手。
    回答准确、简洁、有条理，先给结论，再补充必要细节。
    不确定的事情明确说明，不要编造。
    """,

    "coding":
    """
    你是一名资深软件工程师。
    熟悉常见编程语言、数据结构与算法、系统设计。
    回答以可直接使用的代码和具体工程实践为主，并指出容易踩的坑。
    """,

    "translation":
    """
    你是一名专业翻译。
    在中文与英文之间互译，保持原意、语气与专业术语准确。
    只输出译文，用户明确要求解释时再补充说明。
    """,

    "writing":
    """
    你是一名文字编辑。
    负责润色、改写、调整结构与语气，让表达更清晰自然。
    保留原意，不擅自增删信息。
    """,

    "tutor":
    """
    你是一名耐心导师。
    先讲清概念与原理，再用例子说明，由浅入深。
    必要时指出常见的理解误区。
    """
}

chat_history = []


def chat(message, role):

    global chat_history

    chat_history.append({
        "role": "user",
        "content": message
    })

    system_prompt = roles.get(
        role,
        roles["general"]
    )

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            }
        ] + chat_history
    )

    answer = response.choices[0].message.content

    chat_history.append({
        "role": "assistant",
        "content": answer
    })

    return answer


def chat_with_history(
    message,
    role,
    history=None
):
    """
    带显式历史的多轮聊天。

    与 chat() 的区别：不依赖全局 chat_history，
    历史由调用方（会话服务）从数据库读取后传入。
    """

    system_prompt = roles.get(
        role,
        roles["general"]
    )

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

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages
    )

    return response.choices[0].message.content


def clear_history():

    global chat_history

    chat_history = []


def get_history():

    return chat_history