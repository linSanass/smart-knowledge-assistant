"""
测试公共工具。

异步化之后「构建索引」不再是同步接口：
GET /build-rag 只排队并返回 202，构建结果要去 /documents/status 读。
需要「索引已就绪」的测试统一走 ensure_index，不要各写一份等待逻辑。
"""

import time


def wait_idle(client, timeout=180.0):
    """
    等后台构建结束，返回 /documents/status 的最终内容。

    有界等待，构建卡住时直接失败而不是把测试挂死。
    """

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:

        status = client.get("/documents/status").json()

        if not status["building"]:

            return status

        time.sleep(0.05)

    raise AssertionError(
        f"后台构建 {timeout}s 内未结束"
    )


def ensure_index(client, timeout=180.0):
    """
    确保知识库可用，返回本轮构建结果。

    409 也算成功——说明已经有一次构建在跑，
    调用方的目标只是「索引可用」，不是「这次点击必须由我触发」。
    """

    resp = client.get("/build-rag")

    assert resp.status_code in (202, 409), resp.text

    status = wait_idle(client, timeout=timeout)

    assert status["last_error"] is None, (
        f"构建失败: {status['last_error']}"
    )

    assert status["chunk_count"] > 0, (
        "知识库为空，请确认 backend/uploads 下有 PDF"
    )

    return status["last_result"]
