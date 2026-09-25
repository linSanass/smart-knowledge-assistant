from contextlib import asynccontextmanager

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    status
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, init_db

from services import document_service

from services.chat_service import (
    chat,
    clear_history,
    get_history
)

from services.pdf_service import (
    read_pdf,
    split_pdf
)

from services import rag_service

from services.rag_service import (
    search_chunks,
    rag_chat
)

from routers.conversations import (
    router as conversations_router
)

from routers.documents import (
    router as documents_router
)

from routers.notes import (
    router as notes_router
)

from routers.tools import (
    router as tools_router
)

from routers.agent import (
    router as agent_router
)

from routers.cache import (
    router as cache_router
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

app.include_router(
    documents_router
)

app.include_router(
    notes_router
)

app.include_router(
    tools_router
)

app.include_router(
    agent_router
)

app.include_router(
    cache_router
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
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    保留的旧上传接口。

    为了和多文档知识库保持一致，这里同样会把文件登记进 documents 表。
    新代码请使用 POST /documents。
    """

    content = await file.read()

    file_path = document_service.save_upload(
        content,
        file.filename
    )

    document = document_service.create_document(
        db,
        file.filename,
        file_path
    )

    return {
        "filename": file.filename,
        "document": document_service.serialize_document(
            document
        ),
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

@app.get(
    "/build-rag",
    status_code=status.HTTP_202_ACCEPTED
)
def build_rag(background_tasks: BackgroundTasks):
    """
    手动触发知识库构建（重建 / 重试入口）。

    真正的解析与 embedding 在后台跑，这个请求立即返回 202。
    构建结果看 GET /documents/status 的 last_result / last_error。
    """

    # 已经在构建中就直接拒绝，避免两次构建同时改全局索引
    if rag_service.is_building():

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="知识库正在构建中，请稍后再试"
        )

    background_tasks.add_task(rag_service.run_build_task)

    return {
        "message": "已开始后台构建知识库",
        "build_scheduled": True,
        "status": rag_service.get_index_status()
    }


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