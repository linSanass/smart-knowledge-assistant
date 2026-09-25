import os

from models import Document

# 通过模块引用 UPLOAD_DIR，方便测试时替换上传目录
from services import pdf_service


# =========================
# 查询
# =========================

def list_documents(db):

    return (
        db.query(Document)
        .order_by(
            Document.id.desc()
        )
        .all()
    )


def get_document(db, document_id):

    return db.get(Document, document_id)


def get_document_by_path(db, file_path):

    return (
        db.query(Document)
        .filter(Document.file_path == file_path)
        .first()
    )


# =========================
# 新增
# =========================

def create_document(
    db,
    filename,
    file_path,
    status="pending"
):

    document = Document(
        filename=filename,
        file_path=file_path,
        status=status
    )

    db.add(document)

    db.commit()

    db.refresh(document)

    return document


def unique_file_path(filename):

    base, ext = os.path.splitext(filename)

    path = os.path.join(pdf_service.UPLOAD_DIR, filename)

    index = 1

    # 重名时追加序号，避免覆盖已有文件
    while os.path.exists(path):

        path = os.path.join(
            pdf_service.UPLOAD_DIR,
            f"{base}_{index}{ext}"
        )

        index += 1

    return path


def save_upload(content, filename):
    """
    把上传内容写到 uploads 目录，返回落盘路径。
    """

    os.makedirs(
        pdf_service.UPLOAD_DIR,
        exist_ok=True
    )

    file_path = unique_file_path(filename)

    with open(file_path, "wb") as buffer:

        buffer.write(content)

    return file_path


# =========================
# 更新状态
# =========================

def mark_ready(
    db,
    document,
    chunk_count
):

    document.status = "ready"

    document.chunk_count = chunk_count

    document.error = None

    db.commit()

    db.refresh(document)

    return document


def mark_failed(
    db,
    document,
    error
):

    document.status = "failed"

    document.chunk_count = 0

    document.error = str(error)[:1000]

    db.commit()

    db.refresh(document)

    return document


# =========================
# 删除
# =========================

def delete_document(db, document_id):

    document = get_document(db, document_id)

    if document is None:

        return False

    # 先删磁盘文件，再删数据库记录
    if document.file_path and os.path.exists(
        document.file_path
    ):

        os.remove(document.file_path)

    db.delete(document)

    db.commit()

    return True


# =========================
# 同步 uploads 目录
# =========================

def sync_documents(db):
    """
    把 uploads 目录里还没登记进数据库的 PDF 补登记。

    这样历史遗留的上传文件也能被多文档索引覆盖到。
    """

    created = []

    for filename in pdf_service.list_pdf_files():

        # 按落盘路径去重，避免重名文件被重复登记
        file_path = os.path.join(
            pdf_service.UPLOAD_DIR,
            filename
        )

        if get_document_by_path(db, file_path):

            continue

        created.append(
            create_document(
                db,
                filename,
                file_path
            )
        )

    return created


# =========================
# 序列化
# =========================

def serialize_document(document):

    return {
        "id": document.id,
        "filename": document.filename,
        "chunk_count": document.chunk_count or 0,
        "status": document.status,
        "error": document.error,
        "created_at": (
            document.created_at.isoformat()
            if document.created_at
            else None
        )
    }
