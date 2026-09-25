from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
from openai import OpenAI
import os

# 加载.env
load_dotenv()

# 创建DeepSeek客户端
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

app = FastAPI()

# 允许React访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求数据格式
class ChatRequest(BaseModel):
    message: str

@app.get("/")
def root():
    return {
        "message": "Smart Knowledge Assistant Backend Running"
    }

@app.post("/chat")
def chat(req: ChatRequest):

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "user",
                "content": req.message
            }
        ]
    )

    answer = response.choices[0].message.content

    return {
        "answer": answer
    }