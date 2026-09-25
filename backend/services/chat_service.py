from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

roles = {

    "unity":
    """
    你是一名资深Unity开发工程师。
    熟悉Unity、C#、HybridCLR、Addressables。
    回答尽量工程化。
    """,

    "cpp":
    """
    你是一名资深C++开发工程师。
    熟悉STL、算法、Linux。
    回答贴近面试。
    """,

    "ai":
    """
    你是一名资深AI全栈架构师。
    熟悉React、FastAPI、LangChain、RAG。
    回答尽量工程化。
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
        "你是一名AI助手"
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
        "你是一名AI助手"
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