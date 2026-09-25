from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status
)

from sqlalchemy.orm import Session

from database import get_db

from services import document_service
from services import file_service
from services import rag_service

from services.pdf_service import UPLOAD_DIR


router = APIRouter(
    prefix="/documents",
    tags=["documents"]
)


# =========================
# 上传文件
# =========================

@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    上传知识文件（PDF / TXT / Markdown）并立即返回。

    解析 → 切分 → embedding → FAISS 全部交给后台任务，
    请求本身不等待这些耗时步骤。
    """

    filename = file.filename or ""

    content = await file.read()

    # 扩展名与内容双重校验：
    # 拦掉不支持的后缀、改了后缀的假 PDF、以及伪装成文本的二进制文件
    error = file_service.validate(
        filename,
        content
    )

    if error:

        raise HTTPException(
            status_code=400,
            detail=error
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

    # 交给后台构建。已经在构建中的话，run_build_task 会登记成
    # 「本轮结束后再跑一次」，所以这里无条件排队，不需要判断
    background_tasks.add_task(rag_service.run_build_task)

    return {
        "document": document_service.serialize_document(
            document
        ),
        "message": "上传成功，已提交后台构建知识库",
        "index_stale": index["built"],
        "index_hint": "正在后台构建知识库，请稍候刷新状态",
        "build_scheduled": True,
        "building": rag_service.is_building()
    }


# =========================
# 知识条目列表
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
    background_tasks: BackgroundTasks,
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
    # 否则回答会引用已经删掉的文件。
    # 重建同样走后台，删除请求不再被 embedding 阻塞
    scheduled = False

    if rag_service.get_index_status()["built"]:

        background_tasks.add_task(rag_service.run_build_task)

        scheduled = True

    return {
        "message": "文档已删除",
        "id": document_id,

        # 只是「已排队」，不是「已重建」，真实结果看 /documents/status
        "index_rebuild_scheduled": scheduled,

        # 注意：这是排队前的快照，不代表删除后的最终状态
        "status": rag_service.get_index_status()
    }
