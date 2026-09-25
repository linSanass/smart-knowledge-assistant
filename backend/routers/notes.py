from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status
)

from pydantic import BaseModel

from sqlalchemy.orm import Session

from database import get_db

from services import document_service
from services import rag_service


router = APIRouter(
    prefix="/notes",
    tags=["notes"]
)


class NoteRequest(BaseModel):

    title: str

    content: str


def validate(req):

    title = (req.title or "").strip()

    content = (req.content or "").strip()

    if not title:

        raise HTTPException(
            status_code=400,
            detail="标题不能为空"
        )

    if not content:

        raise HTTPException(
            status_code=400,
            detail="内容不能为空"
        )

    return title, content


# =========================
# 新建手写知识
# =========================

@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED
)
def create_note(
    req: NoteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    保存一条手写知识，并排队重建索引。

    和上传 PDF 一样是异步的：202 表示已排队，
    真正的切分与 embedding 在后台跑，结果看 /documents/status
    """

    title, content = validate(req)

    note = document_service.create_note(
        db,
        title,
        content
    )

    background_tasks.add_task(rag_service.run_build_task)

    return {
        "note": document_service.serialize_document(note),
        "message": "已保存，正在后台更新知识库",
        "build_scheduled": True
    }


# =========================
# 编辑手写知识
# =========================

@router.put(
    "/{note_id}",
    status_code=status.HTTP_202_ACCEPTED
)
def update_note(
    note_id: int,
    req: NoteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    编辑标题或正文。改完同样要重建索引，
    否则检索结果里还是旧内容
    """

    title, content = validate(req)

    note = document_service.update_note(
        db,
        note_id,
        title,
        content
    )

    if note is None:

        raise HTTPException(
            status_code=404,
            detail="笔记不存在"
        )

    background_tasks.add_task(rag_service.run_build_task)

    return {
        "note": document_service.serialize_document(note),
        "message": "已更新，正在后台更新知识库",
        "build_scheduled": True
    }
