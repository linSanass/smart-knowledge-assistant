"""
知识库文件格式验证：PDF / TXT / Markdown 统一进同一个知识库。

覆盖：
1. 三种格式都能上传（202）并进入索引
2. 各自的内容都能被检索到，且来源正确
3. 三种格式同时出现在知识库列表里
4. 不支持的扩展名被拒
5. 伪装成 txt 的二进制内容被拒
6. GBK 编码的 TXT 也能正常读取（中文环境常见）

用临时上传目录隔离，不污染真实数据，跑完自己清理。

不调用 DeepSeek：检索走本地 embedding 与 FAISS。

直接运行：
    cd backend && python tests/test_file_formats.py
"""

import os
import shutil
import sys
import tempfile

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from fastapi.testclient import TestClient

from helpers import wait_idle

# 复用 test_documents 里的最小 PDF 构造，避免两份实现漂移
from test_documents import make_pdf

# 上传目录通过模块属性替换，所以引用模块而不是直接 import 值
from services import pdf_service


# 每个文件一个唯一标记，避免互相干扰
PDF_TOKEN = "PDFTOKENONE"

TXT_TOKEN = "TXTTOKENTWO"

MD_TOKEN = "MDTOKENTHREE"

GBK_TOKEN = "GBKTOKENFOUR"


def upload(client, filename, content):

    return client.post(
        "/documents",
        files={"file": (filename, content, "application/octet-stream")}
    )


def chunk_hit(client, query, token):
    """
    检索 token，返回命中的 (文件名, 片段) 列表。

    只看包含 token 的片段，避免被其它文件的 top_k 结果干扰
    """

    resp = client.get("/search", params={"query": query})

    assert resp.status_code == 200, resp.text

    return [
        (item["filename"], item["chunk"])
        for item in resp.json()["result"]
        if token in item["chunk"]
    ]


def check_upload(client):

    pdf = make_pdf([
        f"{PDF_TOKEN} is a marker inside a PDF file."
    ])

    txt = (
        f"{TXT_TOKEN} 是纯文本文件里的标记。\n"
        "第二行，用来验证多行文本也能被切分。\n"
    ).encode("utf-8")

    md = (
        f"# {MD_TOKEN} 标题\n\n"
        "这是 Markdown 文件里的正文。\n\n"
        "- 列表项一\n"
        "- 列表项二\n"
    ).encode("utf-8")

    # GBK 编码的中文 TXT：中文环境里很常见
    gbk = (
        f"{GBK_TOKEN} 这段是用 GBK 编码保存的中文文本。"
    ).encode("gbk")

    for name, content in (
        ("format.pdf", pdf),
        ("format.txt", txt),
        ("format.md", md),
        ("format_gbk.txt", gbk)
    ):

        resp = upload(client, name, content)

        assert resp.status_code == 202, (name, resp.text)

        body = resp.json()

        assert body["build_scheduled"] is True, body

        # 文件类条目的 kind 都是 "pdf"（历史值，实际表示「文件」）
        assert body["document"]["kind"] == "pdf", body

        print("[OK] 上传", name, "-> 202")

    wait_idle(client)


def check_list(client):

    items = client.get("/documents").json()

    names = {item["filename"] for item in items}

    for expected in (
        "format.pdf",
        "format.txt",
        "format.md",
        "format_gbk.txt"
    ):

        assert expected in names, (expected, names)

    # 都应解析成功
    for item in items:

        assert item["status"] == "ready", item

    print("[OK] 四种文件都在知识库列表里且状态就绪")

    # 文件大小：文本文件也该有值
    txt = next(i for i in items if i["filename"] == "format.txt")

    assert txt["size"] and txt["size"] > 0, txt

    print("[OK] 文本文件也有文件大小:", txt["size"], "字节")


def check_searchable(client):

    cases = [
        ("format.pdf", PDF_TOKEN),
        ("format.txt", TXT_TOKEN),
        ("format.md", MD_TOKEN),
        ("format_gbk.txt", GBK_TOKEN)
    ]

    for filename, token in cases:

        hits = chunk_hit(client, token, token)

        assert hits, f"{filename} 的内容没有进索引（token={token}）"

        assert any(
            name == filename
            for name, _ in hits
        ), (filename, hits)

        print("[OK]", filename, "的内容可被检索到，来源正确")


def check_rejects(client):

    # 不支持的扩展名
    resp = upload(client, "note.docx", b"hello")

    assert resp.status_code == 400, resp.text

    # 改了后缀的假 PDF
    resp = upload(client, "fake.pdf", b"not a pdf")

    assert resp.status_code == 400, resp.text

    # 伪装成 txt 的二进制内容
    resp = upload(client, "fake.txt", b"\x00\x01\x02binary")

    assert resp.status_code == 400, resp.text

    # 大小写扩展名也该认：.TXT 不是非法格式
    resp = upload(client, "upper.TXT", TXT_TOKEN.encode() + b" upper case")

    assert resp.status_code == 202, resp.text

    print("[OK] 不支持的扩展名 / 假 PDF / 二进制内容 被拒，.TXT 大小写可用")


def main():

    tmp_dir = tempfile.mkdtemp(prefix="rag_formats_")

    original_upload_dir = pdf_service.UPLOAD_DIR

    pdf_service.UPLOAD_DIR = tmp_dir

    from main import app

    client = TestClient(app)

    try:

        # 清空 documents 表，从干净状态开始
        from database import SessionLocal
        from models import Document

        db = SessionLocal()

        for row in db.query(Document).all():

            db.delete(row)

        db.commit()

        db.close()

        check_upload(client)

        check_list(client)

        check_searchable(client)

        check_rejects(client)

        print("\n全部测试通过")

    finally:

        # 清掉本次产生的记录：临时目录下的文件都会被删，
        # 记录留着会在下次构建时变成一排 failed 的僵尸条目
        cleanup_test_documents(tmp_dir)

        pdf_service.UPLOAD_DIR = original_upload_dir

        shutil.rmtree(tmp_dir, ignore_errors=True)


def cleanup_test_documents(tmp_dir):
    """
    只清理 file_path 落在临时目录下的记录，不碰真实 uploads 里的。
    """

    try:

        from database import SessionLocal
        from models import Document

        db = SessionLocal()

    except Exception:

        return

    try:

        stale = [
            row
            for row in db.query(Document).all()
            if row.file_path
            and row.file_path.startswith(tmp_dir)
        ]

        for row in stale:

            db.delete(row)

        if stale:

            db.commit()

    except Exception:

        pass

    finally:

        db.close()


if __name__ == "__main__":

    main()
