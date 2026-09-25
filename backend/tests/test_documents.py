"""
多文档知识库验证。

使用临时 uploads 目录和临时文件，不污染真实数据。
会真实调用 DeepSeek 验证 RAG 来源。

直接运行：
    cd backend && python tests/test_documents.py
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

from services import pdf_service


# =========================
# 构造最小可用 PDF
# =========================

def make_pdf(lines):
    """
    手工拼一个合法 PDF，供 pypdf 解析。

    只用 Helvetica + ASCII 文本，保证 extract_text 能取到内容。
    """

    text_ops = "\n".join(
        f"BT /F1 18 Tf 72 {700 - i * 30} Td "
        f"({line}) Tj ET"
        for i, line in enumerate(lines)
    )

    stream = text_ops.encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 612 792] "
            b"/Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        (
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        ),
        (
            b"<< /Type /Font /Subtype /Type1 "
            b"/BaseFont /Helvetica >>"
        )
    ]

    out = bytearray(b"%PDF-1.4\n")

    offsets = []

    for number, body in enumerate(objects, start=1):

        offsets.append(len(out))

        out += (
            f"{number} 0 obj\n".encode()
            + body
            + b"\nendobj\n"
        )

    xref_pos = len(out)

    out += f"xref\n0 {len(objects) + 1}\n".encode()

    out += b"0000000000 65535 f \n"

    for offset in offsets:

        out += f"{offset:010d} 00000 n \n".encode()

    out += (
        f"trailer\n<< /Size {len(objects) + 1} "
        f"/Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()

    return bytes(out)


# =========================
# 测试
# =========================

def main():

    tmp_dir = tempfile.mkdtemp(prefix="rag_uploads_")

    # 隔离上传目录，测试完恢复
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

        # =========================
        # 1. 上传两个 PDF
        # =========================

        pdf_a = make_pdf([
            "ALPHAUNIQUE report about Unity hot update.",
            "HybridCLR is used for this ALPHAUNIQUE project."
        ])

        pdf_b = make_pdf([
            "BETAUNIQUE report about C++ memory model.",
            "RAII and smart pointers are BETAUNIQUE topics."
        ])

        resp = client.post(
            "/documents",
            files={
                "file": ("alpha.pdf", pdf_a, "application/pdf")
            }
        )

        assert resp.status_code == 202, resp.text

        alpha = resp.json()

        alpha_id = alpha["document"]["id"]

        # 上传接口本身不解析：响应体里文档还是 pending，
        # 并且明确告知构建已排队。这条断言替代了原来
        # 「列表里 status 全是 pending」——因为 TestClient 会等后台任务跑完，
        # 那条断言在这里已经不可能成立，留着就是假测试。
        assert alpha["document"]["status"] == "pending", alpha

        assert alpha["build_scheduled"] is True, alpha

        resp = client.post(
            "/documents",
            files={
                "file": ("beta.pdf", pdf_b, "application/pdf")
            }
        )

        assert resp.status_code == 202, resp.text

        beta_id = resp.json()["document"]["id"]

        print("[OK] 上传两个 PDF（202 + 后台构建已排队）")

        # =========================
        # 2. 列表
        # =========================

        resp = client.get("/documents")

        assert resp.status_code == 200

        docs = resp.json()

        assert len(docs) == 2, docs

        names = {
            d["filename"]
            for d in docs
        }

        assert names == {"alpha.pdf", "beta.pdf"}, names

        # 这里不再断言 status == "pending"。
        # TestClient 会等后台任务跑完才返回，走到这行构建早已结束，
        # 文档已经是 ready —— 继续断言 pending 会变成一条永远不成立的假测试。
        # 「上传不同步解析」改由上面的上传响应体断言证明，
        # 「构建进行中的真实中间态」由 test_async_documents.py 的闸门测试覆盖。
        assert all(
            d["status"] in ("pending", "processing", "ready", "failed")
            for d in docs
        ), docs

        print("[OK] PDF 列表 =", sorted(names))

        # =========================
        # 3. 非法文件
        # =========================

        # 原本这里断言 note.txt 被拒（当时只支持 PDF）。
        # TXT 现在是受支持的格式，那条断言已经不成立，
        # 换成「不支持的扩展名」继续守住入口校验

        resp = client.post(
            "/documents",
            files={
                "file": ("note.docx", b"hello", "application/octet-stream")
            }
        )

        assert resp.status_code == 400, "不支持的扩展名未被拦截"

        resp = client.post(
            "/documents",
            files={
                "file": ("fake.pdf", b"not a pdf", "application/pdf")
            }
        )

        assert resp.status_code == 400, "假 PDF 未被拦截"

        # TXT / Markdown 没有魔数可校验，
        # 用含 NUL 字节来识别伪装成文本的二进制内容
        resp = client.post(
            "/documents",
            files={
                "file": ("fake.txt", b"\x00\x01\x02binary", "text/plain")
            }
        )

        assert resp.status_code == 400, "伪装成 txt 的二进制未被拦截"

        print("[OK] 不支持的扩展名 / 假 PDF / 二进制内容 均被拒绝")

        # =========================
        # 4. 构建索引
        # =========================

        resp = client.get("/build-rag")

        assert resp.status_code == 202, resp.text

        assert resp.json()["build_scheduled"] is True, resp.json()

        # 构建结果不在触发响应里了，从状态接口读
        wait_idle(client)

        built = client.get("/documents/status").json()["last_result"]

        assert built["documents"] == 2, built

        assert built["chunk_count"] > 0, built

        assert built["failed"] == [], built

        print("[OK] 构建索引:", built)

        # =========================
        # 5. 文档状态更新为 ready
        # =========================

        docs = client.get("/documents").json()

        assert all(
            d["status"] == "ready"
            for d in docs
        ), docs

        assert all(
            d["chunk_count"] > 0
            for d in docs
        ), docs

        print(
            "[OK] 文档状态 ready, chunk:",
            {d["filename"]: d["chunk_count"] for d in docs}
        )

        # =========================
        # 6. 搜索带来源信息
        # =========================

        resp = client.get(
            "/search",
            params={"query": "ALPHAUNIQUE"}
        )

        assert resp.status_code == 200

        results = resp.json()["result"]

        assert results, "搜索无结果"

        top = results[0]

        assert top["filename"] == "alpha.pdf", top

        assert "chunk" in top

        assert "chunk_index" in top

        print(
            "[OK] 搜索命中最相关来源:",
            top["filename"],
            "chunk_index =", top["chunk_index"]
        )

        resp = client.get(
            "/search",
            params={"query": "BETAUNIQUE"}
        )

        assert resp.json()["result"][0]["filename"] == "beta.pdf"

        print("[OK] 第二个 PDF 也能被检索到")

        # =========================
        # 7. RAG 来源
        # =========================

        resp = client.post(
            "/rag-chat",
            json={"question": "What is HybridCLR in the ALPHAUNIQUE report?"}
        )

        assert resp.status_code == 200

        data = resp.json()

        assert data["answer"].strip()

        assert data["sources"], "RAG 未返回来源"

        assert all(
            "filename" in s and "chunk" in s
            for s in data["sources"]
        ), data["sources"]

        assert data["sources"][0]["filename"] == "alpha.pdf", (
            data["sources"]
        )

        print(
            "[OK] RAG 来源:",
            [
                (s["filename"], s["chunk_index"])
                for s in data["sources"]
            ]
        )

        # =========================
        # 8. 删除 PDF 后索引自动重建
        # =========================

        resp = client.delete(f"/documents/{alpha_id}")

        assert resp.status_code == 200, resp.text

        result = resp.json()

        # 异步后这个字段只表示「重建已排队」，不再是「已重建」
        assert result["index_rebuild_scheduled"] is True, result

        status = wait_idle(client)

        assert status["documents"] == 1, status

        print("[OK] 删除后索引重建:", status)

        resp = client.get("/documents")

        assert len(resp.json()) == 1

        # 文件也应该被删掉
        assert not os.path.exists(
            os.path.join(tmp_dir, "alpha.pdf")
        ), "PDF 文件未从磁盘删除"

        print("[OK] PDF 已从磁盘删除")

        # 已删除的文档不能再被检索到
        resp = client.get(
            "/search",
            params={"query": "ALPHAUNIQUE"}
        )

        filenames = {
            r["filename"]
            for r in resp.json()["result"]
        }

        assert "alpha.pdf" not in filenames, (
            "已删除文档仍可检索: " + str(filenames)
        )

        print("[OK] 已删除文档不再出现在检索结果")

        # =========================
        # 9. 删除不存在的文档
        # =========================

        resp = client.delete("/documents/999999999")

        assert resp.status_code == 404

        print("[OK] 删除不存在文档返回 404")

        # =========================
        # 10. 全部删除后索引为空
        # =========================

        resp = client.delete(f"/documents/{beta_id}")

        assert resp.status_code == 200

        # 删除触发的重建也要等完，否则可能读到上一轮的旧状态
        status = wait_idle(client)

        assert status["built"] is False

        resp = client.post(
            "/rag-chat",
            json={"question": "anything"}
        )

        assert "知识库为空" in resp.json()["answer"]

        print("[OK] 清空后知识库为空")

        print("\n全部测试通过")

    finally:

        pdf_service.UPLOAD_DIR = original_upload_dir

        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":

    main()
