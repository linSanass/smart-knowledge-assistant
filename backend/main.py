from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
from openai import OpenAI

import os

# 读取.env
load_dotenv()

# DeepSeek客户端
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

app = FastAPI()

# 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 聊天历史
chat_history = []

# 角色Prompt
roles = {

    "unity":
    """
    你是一名资深Unity开发工程师。

    熟悉：
    Unity
    C#
    UGUI
    Addressables
    HybridCLR
    性能优化
    游戏开发

    回答尽量工程化。
    """,

    "cpp":
    """
    你是一名资深C++开发工程师。

    熟悉：
    STL
    数据结构
    算法
    Linux
    网络编程

    回答尽量贴近面试。
    """,

    "ai":
    """
    你是一名资深AI全栈架构师。

    熟悉：
    React
    FastAPI
    LangChain
    RAG
    Agent

    回答尽量工程化。
    """,

    "digital":
    """
    你是一名数字孪生专家。

    熟悉：
    Unity数字孪生
    WebSocket
    PLC
    工业互联网
    数据可视化

    回答贴近工业项目。
    """
}


class ChatRequest(BaseModel):
    message: str
    role: str


@app.get("/")
def root():
    return {
        "message": "Smart Knowledge Assistant Running"
    }


@app.post("/chat")
def chat(req: ChatRequest):

    global chat_history

    chat_history.append(
        {
            "role": "user",
            "content": req.message
        }
    )

    system_prompt = roles.get(
        req.role,
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

    chat_history.append(
        {
            "role": "assistant",
            "content": answer
        }
    )

    return {
        "answer": answer
    }


@app.post("/clear")
def clear():

    global chat_history

    chat_history = []

    return {
        "message": "history cleared"
    }


@app.get("/history")
def history():
    return chat_history