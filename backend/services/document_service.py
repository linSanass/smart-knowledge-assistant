import os

from uuid import uuid4

from models import Document

# 通过模块引用 UPLOAD_DIR，方便测试时替换上传目录
from services import pdf_service


# 知识条目的两种类型
KIND_PDF = "pdf"

KIND_NOTE = "note"


def is_note(document):
    """
    是不是手写知识。

    老数据没有 kind（迁移前写入的行），一律当 PDF 处理。
    """

    return (document.kind or KIND_PDF) == KIND_NOTE


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


def create_note(db, title, content):
    """
    新建一条手写知识。

    标题存进 filename、正文存进 content，
    这样下游的 chunk 与来源追踪继续用 filename 作展示名，不必到处分支。
    """

    note = Document(
        filename=title,

        # file_path 列是 NOT NULL，而笔记没有文件。
        # 用一个不会被误认成磁盘路径的哨兵：删除时的 os.path.exists 恒为 False，
        # sync_documents 也不会拿它去和 uploads 里的文件比对
        file_path=f"note://{uuid4().hex}",

        kind=KIND_NOTE,

        content=content,

        status="pending",

        chunk_count=0
    )

    db.add(note)

    db.commit()

    db.refresh(note)

    return note


def update_note(db, note_id, title, content):
    """
    编辑手写知识。找不到或不是笔记则返回 None。
    """

    note = get_document(db, note_id)

    if note is None or not is_note(note):

        return None

    note.filename = title

    note.content = content

    # 正文变了，索引里的旧内容必须重建，所以退回 pending
    note.status = "pending"

    db.commit()

    db.refresh(note)

    return note


def file_size(document):
    """
    文件大小（字节）。笔记没有文件，返回 None。

    实时读盘而不是存一列：省一次迁移，已有数据立刻就有值。
    """

    if is_note(document) or not document.file_path:

        return None

    try:

        return os.path.getsize(document.file_path)

    except OSError:

        # 文件被移走或删掉时不该让整个列表接口挂掉
        return None


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


def mark_processing(db, documents):
    """
    把还没解析成功的文档标成 processing。

    让前端的文档列表在后台构建期间显示「处理中」，
    而不是一直停在「待索引」。
    """

    changed = 0

    for document in documents:

        if document.status in ("pending", "failed"):

            document.status = "processing"

            changed += 1

    if changed:

        db.commit()

    return changed


def reset_processing(db):
    """
    把卡在 processing 的文档退回 pending。

    构建中途崩溃时，这些文档既没 ready 也没 failed，
    不重置的话前端会永远显示「处理中」。
    """

    stuck = (
        db.query(Document)
        .filter(Document.status == "processing")
        .all()
    )

    for document in stuck:

        document.status = "pending"

    if stuck:

        db.commit()

    return len(stuck)


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

    note = is_note(document)

    return {
        "id": document.id,

        # PDF 是文件名，笔记是标题 —— 统一叫 filename，前端按 kind 决定图标
        "filename": document.filename,

        "kind": KIND_NOTE if note else KIND_PDF,

        # 只有笔记有正文。列表接口一并返回，编辑时不必再拉一次详情
        "content": document.content if note else None,

        # 字节数；笔记没有文件所以是 None
        "size": file_size(document),

        "chunk_count": document.chunk_count or 0,

        "status": document.status,

        "error": document.error,

        "created_at": (
            document.created_at.isoformat()
            if document.created_at
            else None
        )
    }
