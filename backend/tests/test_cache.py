"""
Redis 缓存验证。

覆盖：
1. knowledge_search 第一次 Cache Miss，第二次 Cache Hit
2. 结果一致（缓存没有改变返回值）
3. TTL 生效
4. 重建索引后缓存失效，不会命中旧知识库内容
5. Redis 不可用时自动降级，knowledge_search 仍然可用
6. /cache/stats 与 /cache/clear

直接运行：
    cd backend && python tests/test_cache.py
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

from services import cache_service

from services import tools


def check_redis_available(client):

    stats = client.get("/cache/stats").json()

    assert stats["enabled"] is True, (
        "Redis 不可用，请先启动 Redis (127.0.0.1:6379)"
    )

    print("[OK] Redis 可用:", stats["url"], "TTL =", stats["ttl"])

    return stats


def check_hit_and_miss(client):

    client.post("/cache/clear")

    client.get("/build-rag")

    query = "HybridCLR 是什么"

    # 第一次：未命中
    first = tools.knowledge_search(query, top_k=2)

    assert first["cached"] is False, "第一次应该是 Cache Miss"

    print("[OK] 第一次 Cache Miss")

    # 第二次：命中
    second = tools.knowledge_search(query, top_k=2)

    assert second["cached"] is True, "第二次应该是 Cache Hit"

    print("[OK] 第二次 Cache Hit")

    # 内容必须一致（cached 标记除外）
    a = {k: v for k, v in first.items() if k != "cached"}

    b = {k: v for k, v in second.items() if k != "cached"}

    assert a == b, "缓存前后的结果不一致"

    print("[OK] 缓存结果与真实检索一致")

    # 统计
    stats = client.get("/cache/stats").json()

    assert stats["hits"] >= 1, stats

    assert stats["misses"] >= 1, stats

    assert 0 <= stats["hit_rate"] <= 1, stats

    print(
        "[OK] 统计: hits =", stats["hits"],
        "misses =", stats["misses"],
        "hit_rate =", stats["hit_rate"]
    )

    # 不同 top_k 应该是不同的 key
    other = tools.knowledge_search(query, top_k=1)

    assert other["cached"] is False, (
        "top_k 不同却命中了同一个缓存 key"
    )

    print("[OK] 不同 top_k 使用不同缓存 key")


def check_ttl(client):

    key = cache_service.make_key("ttl-probe", 3)

    assert key is not None

    assert cache_service.set_json(
        key,
        {"probe": True},
        ttl=60
    )

    client_ = cache_service.get_client()

    ttl = client_.ttl(key)

    assert 0 < ttl <= 60, f"TTL 不正确: {ttl}"

    print("[OK] TTL 生效:", ttl, "秒")

    # 清理这个探针 key
    client_.delete(key)


def check_invalidation(client):

    client.get("/build-rag")

    query = "Addressables 的作用"

    tools.knowledge_search(query, top_k=2)

    assert (
        tools.knowledge_search(query, top_k=2)["cached"]
        is True
    )

    print("[OK] 重建索引前可以命中缓存")

    # 重建索引 → 必须失效
    client.get("/build-rag")

    assert (
        tools.knowledge_search(query, top_k=2)["cached"]
        is False
    ), "重建索引后仍命中旧缓存"

    print("[OK] 重建索引后缓存失效，不再命中旧内容")

    stats = client.get("/cache/stats").json()

    assert stats["invalidations"] >= 1, stats

    print("[OK] 失效次数已记录:", stats["invalidations"])


def check_disabled_fallback():

    # 指向一个不存在的 Redis，模拟 Redis 挂了
    original_url = cache_service.REDIS_URL

    original_client = cache_service._client

    original_failure = cache_service._last_failure

    try:

        cache_service.REDIS_URL = "redis://127.0.0.1:6399/0"

        cache_service._client = None

        cache_service._last_failure = 0.0

        assert cache_service.get_client() is None, (
            "连不上 Redis 时应该返回 None"
        )

        assert cache_service.is_enabled() is False

        # 缓存不可用时，检索仍然要正常工作
        result = tools.knowledge_search(
            "HybridCLR",
            top_k=2
        )

        assert result["found"] is True, result

        assert result["cached"] is False, result

        assert result["results"], result

        print("[OK] Redis 不可用时自动降级，knowledge_search 仍返回结果")

        # 连续失败后不会每次都重试
        import time

        started = time.monotonic()

        for _ in range(5):

            cache_service.get_client()

        elapsed = time.monotonic() - started

        assert elapsed < 0.5, (
            f"失败后仍在反复重连，耗时 {elapsed:.2f}s"
        )

        print("[OK] 失败后有重试冷却，不会反复阻塞")

    finally:

        cache_service.REDIS_URL = original_url

        cache_service._client = original_client

        cache_service._last_failure = original_failure


def main():

    from main import app

    client = TestClient(app)

    check_redis_available(client)

    check_hit_and_miss(client)

    check_ttl(client)

    check_invalidation(client)

    check_disabled_fallback()

    print("\n全部测试通过")


if __name__ == "__main__":

    main()
