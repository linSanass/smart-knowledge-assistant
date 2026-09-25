from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile
)

from sqlalchemy.orm import Session

from database import get_db

from services import document_service
from services import rag_service

from services.pdf_service import UPLOAD_DIR


router = APIRouter(
    prefix="/documents",
    tags=["documents"]
)


# =========================
# 上传 PDF
# =========================

@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    filename = file.filename or ""

    if not filename.lower().endswith(".pdf"):

        raise HTTPException(
            status_code=400,
            detail="只支持 PDF 文件"
        )

    content = await file.read()

    # 校验文件头，避免改了扩展名的假 PDF
    if not content.startswith(b"%PDF"):

        raise HTTPException(
            status_code=400,
            detail="文件内容不是合法的 PDF"
        )

    file_path = document_service.save_upload(
        content,
        filename
    )

    document = document_service.create_document(
        db,
        filename,
        file_path
    )

    # 知识库里有旧内容时，索引已经和新文档对不上了
    index = rag_service.get_index_status()

    return {
        "document": document_service.serialize_document(
            document
        ),
        "message": "上传成功",
        "index_stale": index["built"],
        "index_hint": (
            "请点击「构建知识库」以纳入新文档"
            if index["built"]
            else "请点击「构建知识库」"
        )
    }


# =========================
# PDF 列表
# =========================

@router.get("")
def list_documents(
    db: Session = Depends(get_db)
):

    return [
        document_service.serialize_document(d)
        for d in document_service.list_documents(db)
    ]


# =========================
# 知识库索引状态
# =========================

@router.get("/status")
def index_status():

    return rag_service.get_index_status()


# =========================
# 删除 PDF
# =========================

@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db)
):

    if not document_service.delete_document(
        db,
        document_id
    ):

        raise HTTPException(
            status_code=404,
            detail="文档不存在"
        )

    # 索引里还留着这个文档的 chunk，必须重建，
    # 否则回答会引用已经删掉的文件
    rebuilt = False

    if rag_service.get_index_status()["built"]:

        rag_service.build_vector_store()

        rebuilt = True

    return {
        "message": "文档已删除",
        "id": document_id,
        "index_rebuilt": rebuilt,
        "status": rag_service.get_index_status()
    }
