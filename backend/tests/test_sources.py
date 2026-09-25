"""
RAG Sources 契约验证。

约定：
    RAG API 返回 {"answer": "...", "sources": [...]}
    每个 source 至少包含 filename 与 chunk

直接运行：
    cd backend && python tests/test_sources.py
"""

import os
import re
import sys

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from fastapi.testclient import TestClient

from helpers import ensure_index

from services import document_service
from services.rag_service import serialize_source


REQUIRED_FIELDS = (
    "document_id",
    "filename",
    "chunk_index",
    "chunk"
)


def check_serialize():

    source = serialize_source({
        "document_id": 1,
        "filename": "a.pdf",
        "chunk_index": 2,
        "chunk": "hello",
        # 检索内部字段不应该泄漏到 API
        "distance": 0.5
    })

    assert set(source.keys()) == set(REQUIRED_FIELDS), source

    assert "distance" not in source

    print("[OK] serialize_source 字段固定:", sorted(source))


def check_rag_endpoint(client):

    resp = client.post(
        "/rag-chat",
        json={"question": "What is HybridCLR?"}
    )

    assert resp.status_code == 200, resp.text

    data = resp.json()

    assert set(data.keys()) == {"answer", "sources"}, data.keys()

    assert isinstance(data["sources"], list)

    assert data["sources"], "RAG 未返回来源"

    assert len(data["sources"]) <= 3, "来源数量应受 top_k 限制"

    for source in data["sources"]:

        for field in REQUIRED_FIELDS:

            assert field in source, (
                f"source 缺少字段 {field}: {source}"
            )

        assert source["filename"], source

        assert source["chunk"].strip(), source

        assert isinstance(source["chunk_index"], int), source

    print(
        "[OK] /rag-chat 来源:",
        [
            (s["filename"], s["chunk_index"])
            for s in data["sources"]
        ]
    )

    # 命中的 chunk 必须真的来自该 PDF
    from services.pdf_service import read_pdf_file

    from database import SessionLocal

    db = SessionLocal()

    try:

        top = data["sources"][0]

        document = document_service.get_document(
            db,
            top["document_id"]
        )

        assert document is not None, "来源 document_id 不存在"

        assert document.filename == top["filename"], (
            "来源文件名与 document_id 不一致"
        )

        text = read_pdf_file(document.file_path)

        # 去掉空白后比对，避免 PDF 换行差异
        normalized = re.sub(r"\s+", "", text)

        assert re.sub(r"\s+", "", top["chunk"]) in normalized, (
            "命中的 chunk 并非来自该 PDF"
        )

        print("[OK] 来源可回溯到真实 PDF:", document.filename)

    finally:

        db.close()


def check_conversation_roundtrip(client):

    conversation = client.post(
        "/conversations",
        json={}
    ).json()

    conversation_id = conversation["id"]

    try:

        resp = client.post(
            f"/conversations/{conversation_id}/messages",
            json={
                "message": "What is Addressables?",
                "mode": "rag"
            }
        )

        assert resp.status_code == 200, resp.text

        sent = resp.json()["sources"]

        assert sent, "会话消息未返回来源"

        # 重新读取历史，来源结构必须保持一致
        detail = client.get(
            f"/conversations/{conversation_id}"
        ).json()

        assistant = [
            m for m in detail["messages"]
            if m["role"] == "assistant"
        ][0]

        assert assistant["sources"] == sent, (
            "来源未正确持久化/还原"
        )

        print(
            "[OK] 会话中来源可持久化并原样还原:",
            len(sent),
            "条"
        )

    finally:

        client.delete(f"/conversations/{conversation_id}")


def main():

    check_serialize()

    from main import app

    client = TestClient(app)

    # 构建已异步化：只保证索引可用，结果从 /documents/status 读
    ensure_index(client)

    check_rag_endpoint(client)

    check_conversation_roundtrip(client)

    print("\n全部测试通过")


if __name__ == "__main__":

    main()
