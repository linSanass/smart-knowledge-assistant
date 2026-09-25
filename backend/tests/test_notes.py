"""
手写知识（笔记）验证。

覆盖知识库管理的功能 4 / 5 / 6：
4. 新建知识 → 保存后能被检索到
5. 编辑知识 → 新内容可检索、旧内容从索引里消失
6. 笔记与 PDF 统一出现在同一个列表里

以及删除、参数校验、清理。

不调用 DeepSeek：检索走的是本地 embedding 与 FAISS。

需要 MySQL 与 backend/uploads 下的 PDF（要建索引）。

直接运行：
    cd backend && python tests/test_notes.py
"""

import os
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

from helpers import ensure_index, wait_idle


# 唯一标记，避免和已有内容撞车
TITLE = "NOTETITLEGAMMA 手写知识测试"

CONTENT = "NOTETOKENALPHA 这条是用来验证手写知识能不能进检索索引的。"

EDITED_CONTENT = "NOTETOKENBETA 这是编辑之后的正文，旧标记应该不再出现。"


def chunks_text(client, query):

    resp = client.get(
        "/search",
        params={"query": query}
    )

    assert resp.status_code == 200, resp.text

    return [
        item["chunk"]
        for item in resp.json()["result"]
    ]


def hits(client, query, token):

    return any(
        token in chunk
        for chunk in chunks_text(client, query)
    )


def check_create(client, created):

    resp = client.post(
        "/notes",
        json={"title": TITLE, "content": CONTENT}
    )

    assert resp.status_code == 202, resp.text

    data = resp.json()

    assert data["build_scheduled"] is True, data

    note = data["note"]

    assert note["kind"] == "note", note

    assert note["filename"] == TITLE, note

    assert note["content"] == CONTENT, note

    # 笔记没有文件，大小应为 None
    assert note["size"] is None, note

    created.append(note["id"])

    print("[OK] 新建笔记 -> 202, kind=note, size=None")

    wait_idle(client)

    return note["id"]


def check_unified_list(client):

    resp = client.get("/documents")

    assert resp.status_code == 200, resp.text

    items = resp.json()

    kinds = {item["kind"] for item in items}

    assert "note" in kinds, items

    assert "pdf" in kinds, (
        "列表里没有 PDF，确认 backend/uploads 下有文件: " + str(kinds)
    )

    # 两种类型都带齐了详情页需要的字段
    for item in items:

        for key in ("filename", "kind", "status", "created_at"):

            assert key in item, (key, item)

    note = next(i for i in items if i["kind"] == "note")

    assert note["filename"] == TITLE, note

    print(
        "[OK] 统一列表：笔记与 PDF 共存，共",
        len(items), "条"
    )


def check_searchable(client):

    assert hits(client, "NOTETOKENALPHA", "NOTETOKENALPHA"), (
        "笔记正文没有进入索引"
    )

    print("[OK] 笔记正文可被检索到")

    # 标题也进了索引，按标题关键词应该能命中
    assert hits(client, "NOTETITLEGAMMA", "NOTETOKENALPHA"), (
        "笔记标题没有进入索引"
    )

    print("[OK] 笔记标题也能被检索到")

    # 来源名应该是笔记标题（复用 filename 字段）
    resp = client.get(
        "/search",
        params={"query": "NOTETOKENALPHA"}
    )

    filenames = {
        item["filename"]
        for item in resp.json()["result"]
    }

    assert TITLE in filenames, filenames

    print("[OK] 来源名显示为笔记标题:", TITLE)


def check_edit(client, note_id):

    resp = client.put(
        f"/notes/{note_id}",
        json={
            "title": TITLE,
            "content": EDITED_CONTENT
        }
    )

    assert resp.status_code == 202, resp.text

    assert resp.json()["build_scheduled"] is True

    # 改完应退回 pending，等重建
    assert resp.json()["note"]["content"] == EDITED_CONTENT

    print("[OK] 编辑笔记 -> 202")

    wait_idle(client)

    assert hits(client, "NOTETOKENBETA", "NOTETOKENBETA"), (
        "编辑后的新内容没有进索引"
    )

    print("[OK] 编辑后的新内容可被检索到")

    # 旧内容必须从索引里消失，否则回答会引用已删除的正文
    assert not hits(client, "NOTETOKENALPHA", "NOTETOKENALPHA"), (
        "编辑后旧内容仍然留在索引里"
    )

    print("[OK] 旧内容已从索引中移除")


def check_validation(client):

    resp = client.post(
        "/notes",
        json={"title": "  ", "content": "有内容"}
    )

    assert resp.status_code == 400, resp.text

    resp = client.post(
        "/notes",
        json={"title": "有标题", "content": "   "}
    )

    assert resp.status_code == 400, resp.text

    print("[OK] 空标题 / 空内容返回 400")

    resp = client.put(
        "/notes/99999999",
        json={"title": "x", "content": "y"}
    )

    assert resp.status_code == 404, resp.text

    print("[OK] 编辑不存在的笔记返回 404")


def check_delete(client, note_id):

    resp = client.delete(f"/documents/{note_id}")

    assert resp.status_code == 200, resp.text

    wait_idle(client)

    items = client.get("/documents").json()

    assert all(
        item["id"] != note_id
        for item in items
    ), "删除后仍出现在列表里"

    print("[OK] 删除后从列表消失")

    assert not hits(client, "NOTETOKENBETA", "NOTETOKENBETA"), (
        "删除后内容仍留在索引里"
    )

    print("[OK] 删除后内容已移出索引")


def check_file_size(client):

    items = client.get("/documents").json()

    pdf = next(
        (i for i in items if i["kind"] == "pdf"),
        None
    )

    if pdf is None:

        print("[SKIP] 没有 PDF，跳过文件大小检查")

        return

    assert pdf["size"] is None or pdf["size"] > 0, pdf

    print("[OK] PDF 文件大小:", pdf["size"], "字节")


def main():

    # 从可用索引开始，避免拿一个空知识库做检索断言
    from main import app

    client = TestClient(app)

    ensure_index(client)

    created = []

    try:

        note_id = check_create(client, created)

        check_unified_list(client)

        check_searchable(client)

        check_edit(client, note_id)

        check_validation(client)

        check_delete(client, note_id)

        created.remove(note_id)

        check_file_size(client)

        print("\n全部测试通过")

    finally:

        # 清掉自己建的记录，别给下一次运行留垃圾
        for note_id in created:

            client.delete(f"/documents/{note_id}")


if __name__ == "__main__":

    main()
