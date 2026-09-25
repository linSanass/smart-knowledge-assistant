from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File
from services.rag_service import (
    build_vector_store
)
import os

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
    search_chunks
)

app = FastAPI()

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


class ChatRequest(BaseModel):
    message: str
    role: str


@app.get("/")
def root():

    return {
        "message": "Smart Knowledge Assistant Running"
    }


@app.post("/chat")
def chat_api(req: ChatRequest):

    answer = chat(
        req.message,
        req.role
    )

    return {
        "answer": answer
    }


@app.get("/history")
def history():

    return get_history()


@app.post("/clear")
def clear():

    clear_history()

    return {
        "message": "history cleared"
    }


@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...)
):

    os.makedirs(
        "uploads",
        exist_ok=True
    )

    save_path = f"uploads/{file.filename}"

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


@app.get("/read-pdf")
def read_pdf_api():

    text = read_pdf()

    if isinstance(text, dict):
        return text

    return {
        "content": text[:5000]
    }


@app.get("/split-pdf")
def split_pdf_api():

    return split_pdf()


@app.get("/build-rag")
def build_rag():
    return build_vector_store()


@app.get("/search")
def search(query: str):

    result = search_chunks(query)

    return {
        "result": result
    }