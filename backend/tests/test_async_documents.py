"""
异步 PDF 处理验证。

为什么单独一个文件、而且不用 TestClient：
    TestClient 会等后台任务跑完才返回响应，
    因此它无法观察「请求已返回、处理还没结束」这个窗口，
    用它能写出的只能是通过的假测试。

    这里改用 httpx.AsyncClient + ASGITransport，自己控制事件循环，
    再用 threading.Event 当闸门把后台构建冻住。
    同步的后台任务跑在 Starlette 线程池里，事件循环是空闲的，
    所以「构建被冻住时其它 HTTP 请求仍能正常响应」是可以被真正观察到的 ——
    这正是 uvicorn 下的真实行为。

覆盖：
1. 构建进行中时，HTTP 请求不被阻塞（闸门证明，不靠 sleep 计时）
2. 构建进行中重复触发返回 409
3. 构建进行中再次上传不会丢（结束后补跑一轮）
4. 构建崩溃可恢复：building 归位、last_error 记录、之后还能重建
5. 坏 PDF 被隔离，好 PDF 不受影响
6. 正常路径：上传 → 轮询 → ready → 可检索

直接运行：
    cd backend && python tests/test_async_documents.py
"""

import asyncio
import os
import shutil
import sys
import tempfile
import threading
import time

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

import httpx

from services import pdf_service
from services import rag_service

# 复用 test_documents 里的最小 PDF 构造，避免两份实现漂移
from test_documents import make_pdf


class Gate:
    """
    把后台构建冻在中间的可控闸门。

    比 sleep 可靠：断言不依赖任何时间阈值，
    只要闸门没放行，构建就一定没结束。
    """

    def __init__(self, result=None, error=None):

        self.started = threading.Event()

        self.gate = threading.Event()

        self.calls = []

        self.active = []

        self.max_active = 0

        self.result = result or {
            "message": "stub",
            "chunk_count": 7,
            "documents": 2,
            "failed": []
        }

        self.error = error

    def __call__(self):

        self.calls.append(1)

        self.active.append(1)

        self.max_active = max(
            self.max_active,
            len(self.active)
        )

        self.started.set()

        assert self.gate.wait(30), "闸门超时未放行，构建被挂死"

        self.active.pop()

        if self.error:

            raise self.error

        return self.result


def install(build):
    """替换构建实现，返回还原函数。"""

    original = rag_service.build_vector_store

    rag_service.build_vector_store = build

    return lambda: setattr(
        rag_service,
        "build_vector_store",
        original
    )


async def wait_idle(client, timeout=60.0):

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:

        status = (await client.get(
            "/documents/status"
        )).json()

        if not status["building"]:

            return status

        await asyncio.sleep(0.05)

    raise AssertionError("后台构建超时未结束")


def upload(client, name):

    pdf = make_pdf([f"{name} unique content for async test."])

    return client.post(
        "/documents",
        files={"file": (name, pdf, "application/pdf")}
    )


# =========================
# 1 + 2 + 3. 非阻塞、409、不丢上传
# =========================

async def check_non_blocking(client):

    gate = Gate()

    restore = install(gate)

    try:

        upload_task = asyncio.create_task(
            upload(client, "first.pdf")
        )

        # 等构建真的跑起来并停在闸门上
        started = await asyncio.to_thread(
            gate.started.wait,
            15
        )

        assert started, "后台上传没有触发构建"

        assert not gate.gate.is_set()

        assert rag_service.is_building() is True

        # ---- 关键断言 ----
        # 构建被冻住时，状态接口必须仍然能立刻响应。
        # 能拿到响应本身就是「HTTP 没有被 PDF 处理阻塞」的证据
        probe_started = time.monotonic()

        status = (await client.get("/documents/status")).json()

        probe_elapsed = time.monotonic() - probe_started

        assert status["building"] is True, status

        assert probe_elapsed < 2.0, (
            f"构建期间状态接口被拖慢到 {probe_elapsed:.2f}s"
        )

        print(
            "[OK] 构建进行中状态接口仍可响应，耗时 "
            f"{probe_elapsed * 1000:.0f}ms"
        )

        # 上传接口已经提交并返回，文档还没被解析
        docs = (await client.get("/documents")).json()

        assert len(docs) == 1, docs

        assert docs[0]["status"] in (
            "pending",
            "processing"
        ), docs

        print("[OK] 构建进行中文档处于未完成状态:", docs[0]["status"])

        # 构建中被再次触发 -> 409
        conflict = await client.get("/build-rag")

        assert conflict.status_code == 409, conflict.text

        print("[OK] 构建中重复触发返回 409")

        # 构建中再次上传 -> 202，不阻塞也不丢
        second = await upload(client, "second.pdf")

        assert second.status_code == 202, second.text

        assert second.json()["build_scheduled"] is True

        print("[OK] 构建中再次上传返回 202，不会被拒")

        # 放行
        gate.gate.set()

        first = await upload_task

        assert first.status_code == 202, first.text

        final = await wait_idle(client)

        assert final["last_result"]["chunk_count"] == 7, final

        # 第二次上传登记的重跑被消费掉了，没有丢
        assert len(gate.calls) == 2, (
            f"重跑请求丢失，构建只跑了 {len(gate.calls)} 次"
        )

        # 两次构建没有重叠执行
        assert gate.max_active == 1, (
            f"构建被并发执行了，峰值 {gate.max_active}"
        )

        print(
            "[OK] 构建结束后补跑一轮，未丢上传；"
            f"峰值并发 = {gate.max_active}"
        )

    finally:

        gate.gate.set()

        restore()


# =========================
# 4. 崩溃可恢复
# =========================

async def check_crash_recovery(client):

    gate = Gate(error=RuntimeError("boom"))

    restore = install(gate)

    try:

        task = asyncio.create_task(upload(client, "crash.pdf"))

        assert await asyncio.to_thread(gate.started.wait, 15)

        gate.gate.set()

        resp = await task

        assert resp.status_code == 202, resp.text

        status = await wait_idle(client)

        assert status["last_error"] is not None, status

        assert "boom" in status["last_error"], status

        assert status["last_result"] is None, status

        # 崩溃后必须能再次构建，否则一次异常就永久锁死
        assert status["building"] is False, status

        print("[OK] 构建崩溃后 building 归位:", status["last_error"])

    finally:

        gate.gate.set()

        restore()

    # 崩溃之后还能正常重建
    resp = await client.get("/build-rag")

    assert resp.status_code == 202, resp.text

    status = await wait_idle(client)

    assert status["last_error"] is None, status

    assert status["last_result"] is not None, status

    print("[OK] 崩溃后可正常重建，未被永久锁死")


# =========================
# 5. 坏 PDF 隔离
# =========================

async def check_bad_pdf(client):

    good = await upload(client, "good.pdf")

    assert good.status_code == 202, good.text

    # 骗过文件头校验的坏 PDF：只有 %PDF 前缀，内容不是合法 PDF
    broken = await client.post(
        "/documents",
        files={
            "file": (
                "broken.pdf",
                b"%PDF-1.4\nthis is not a real pdf",
                "application/pdf"
            )
        }
    )

    assert broken.status_code == 202, broken.text

    status = await wait_idle(client)

    assert status["last_result"]["failed"] == ["broken.pdf"], status

    docs = {
        d["filename"]: d
        for d in (await client.get("/documents")).json()
    }

    assert docs["broken.pdf"]["status"] == "failed", docs["broken.pdf"]

    assert docs["broken.pdf"]["error"], docs["broken.pdf"]

    assert docs["good.pdf"]["status"] == "ready", docs["good.pdf"]

    assert docs["good.pdf"]["chunk_count"] > 0, docs["good.pdf"]

    print(
        "[OK] 坏 PDF 被隔离:",
        docs["broken.pdf"]["error"][:60]
    )

    # 好文档不受影响，仍然可检索
    found = (await client.get(
        "/search",
        params={"query": "good.pdf unique content"}
    )).json()["result"]

    assert any(
        r["filename"] == "good.pdf"
        for r in found
    ), found

    print("[OK] 好文档仍可检索，坏文件未污染索引")


# =========================
# 6. 正常路径 + 状态接口契约
# =========================

async def check_happy_path(client):

    status = await client.get("/documents/status")

    assert status.status_code == 200

    body = status.json()

    for key in (
        "built",
        "chunk_count",
        "documents",
        "building",
        "started_at",
        "finished_at",
        "last_result",
        "last_error"
    ):

        assert key in body, f"状态接口缺少字段 {key}: {body}"

    print("[OK] /documents/status 字段齐全:", sorted(body))

    resp = await upload(client, "happy.pdf")

    assert resp.status_code == 202, resp.text

    assert resp.json()["document"]["status"] == "pending", resp.json()

    print("[OK] 上传响应体仍是 pending，证明接口没有同步解析")

    status = await wait_idle(client)

    assert status["building"] is False, status

    assert status["last_error"] is None, status

    docs = (await client.get("/documents")).json()

    assert any(
        d["filename"] == "happy.pdf" and d["status"] == "ready"
        for d in docs
    ), docs

    print("[OK] 后台构建完成，文档 ready")


# =========================
# 7. processing 状态机
# =========================

def check_processing_status():
    """
    直接验证 processing 的进入与回退。

    真实构建太快，轮询几乎抓不到 processing 这个中间态，
    与其写一条靠运气才过的断言，不如直接验证状态机本身。
    """

    from database import SessionLocal
    from models import Document
    from services import document_service

    db = SessionLocal()

    try:

        probe = document_service.create_document(
            db,
            "processing-probe.pdf",
            os.path.join(pdf_service.UPLOAD_DIR, "processing-probe.pdf")
        )

        try:

            assert probe.status == "pending", probe.status

            changed = document_service.mark_processing(db, [probe])

            assert changed == 1, changed

            db.refresh(probe)

            assert probe.status == "processing", probe.status

            # 构建崩溃时靠它把卡住的文档退回可重试状态
            reverted = document_service.reset_processing(db)

            assert reverted >= 1, reverted

            db.refresh(probe)

            assert probe.status == "pending", probe.status

            print("[OK] processing 可进入也可回退，不会永久卡住")

        finally:

            db.delete(probe)

            db.commit()

    finally:

        db.close()


# =========================
# 主流程
# =========================

async def run():

    tmp_dir = tempfile.mkdtemp(prefix="rag_async_")

    original_upload_dir = pdf_service.UPLOAD_DIR

    pdf_service.UPLOAD_DIR = tmp_dir

    from main import app

    transport = httpx.ASGITransport(app=app)

    try:

        # 清空 documents 表，从干净状态开始
        from database import SessionLocal
        from models import Document

        db = SessionLocal()

        for row in db.query(Document).all():

            db.delete(row)

        db.commit()

        db.close()

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            timeout=120.0
        ) as client:

            await check_non_blocking(client)

            await check_crash_recovery(client)

            await check_bad_pdf(client)

            await check_happy_path(client)

            await asyncio.to_thread(check_processing_status)

    finally:

        pdf_service.UPLOAD_DIR = original_upload_dir

        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():

    asyncio.run(run())

    print("\n全部测试通过")


if __name__ == "__main__":

    main()
