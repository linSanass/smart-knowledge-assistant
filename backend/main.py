from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

from database import init_db

from services.chat_service import (
    chat,
    clear_history,
    get_history
)

from services.pdf_service import (
    read_pdf,
    split_pdf
)

from services.rag_service import (
    build_vector_store,
    search_chunks,
    rag_chat
)

from routers.conversations import (
    router as conversations_router
)


# =========================
# 生命周期：启动时建表
# =========================

@asynccontextmanager
async def lifespan(app: FastAPI):

    init_db()

    yield


# =========================
# 创建 FastAPI
# =========================

app = FastAPI(
    title="Smart Knowledge Assistant",
    description="PDF RAG 知识库问答后端",
    version="1.0.0",
    lifespan=lifespan
)


# =========================
# CORS 跨域配置
# =========================

app.add_middleware(
    CORSMiddleware,

    # React + Vite 前端
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# =========================
# 路由
# =========================

app.include_router(
    conversations_router
)


# =========================
# 请求数据结构
# =========================

class ChatRequest(BaseModel):
    message: str
    role: str


class RagRequest(BaseModel):
    question: str


# =========================
# 根目录
# =========================

@app.get("/")
def root():

    return {
        "message": "Smart Knowledge Assistant Running"
    }


# =========================
# 普通聊天
# =========================

@app.post("/chat")
def chat_api(req: ChatRequest):

    answer = chat(
        req.message,
        req.role
    )

    return {
        "answer": answer
    }


# =========================
# 获取聊天历史
# =========================

@app.get("/history")
def history():

    return get_history()


# =========================
# 清空聊天历史
# =========================

@app.post("/clear")
def clear():

    clear_history()

    return {
        "message": "history cleared"
    }


# =========================
# 上传 PDF
# =========================

@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...)
):

    # 创建 uploads 文件夹
    os.makedirs(
        "uploads",
        exist_ok=True
    )

    # 保存路径
    save_path = os.path.join(
        "uploads",
        file.filename
    )

    # 保存 PDF
    with open(
        save_path,
        "wb"
    ) as buffer:

        content = await file.read()

        buffer.write(content)

    return {
        "filename": file.filename,
        "message": "上传成功"
    }


# =========================
# 读取 PDF
# =========================

@app.get("/read-pdf")
def read_pdf_api():

    text = read_pdf()

    # 如果 pdf_service 本身返回错误信息
    if isinstance(text, dict):

        return text

    return {
        "content": text[:5000]
    }


# =========================
# 切分 PDF
# =========================

@app.get("/split-pdf")
def split_pdf_api():

    return split_pdf()


# =========================
# 创建 RAG 向量数据库
# =========================

@app.get("/build-rag")
def build_rag():

    return build_vector_store()


# =========================
# 搜索知识库
# =========================

@app.get("/search")
def search(query: str):

    result = search_chunks(query)

    return {
        "result": result
    }


# =========================
# RAG 问答
# =========================

@app.post("/rag-chat")
def rag_chat_api(
    req: RagRequest
):

    result = rag_chat(
        req.question
    )

    return result