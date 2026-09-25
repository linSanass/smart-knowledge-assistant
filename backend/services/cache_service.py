"""
Redis 缓存。

只缓存 knowledge_search 的检索结果，不迁移 MySQL 里的任何数据。

设计要点：
    - Redis 连不上时自动降级为「不使用缓存」，不影响主流程
    - 命中 / 未命中 / 错误都会计数，可通过 /cache/stats 查看
    - 用版本号做失效：重建索引时 version 自增，
      旧 key 自然不再被读取，不需要遍历删除
"""

import hashlib
import json
import os
import time

from dotenv import load_dotenv

import redis


load_dotenv()


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://127.0.0.1:6379/0"
)

# 缓存有效期（秒）
CACHE_TTL = int(
    os.getenv("CACHE_TTL", "300")
)

KEY_PREFIX = "ska:knowledge_search"

VERSION_KEY = f"{KEY_PREFIX}:version"

# Redis 连续失败后，多久才重新尝试连接
RETRY_INTERVAL = 30


_client = None

_last_failure = 0.0

_stats = {
    "hits": 0,
    "misses": 0,
    "errors": 0,
    "sets": 0,
    "invalidations": 0
}


# =========================
# 连接
# =========================

def get_client():
    """
    返回可用的 Redis 客户端。

    连不上时返回 None，调用方按「没有缓存」处理，
    并且 30 秒内不再重复尝试，避免每次都卡在连接超时上。
    """

    global _client
    global _last_failure

    if _client is not None:

        return _client

    if time.monotonic() - _last_failure < RETRY_INTERVAL:

        return None

    try:

        client = redis.Redis.from_url(
            REDIS_URL,

            # Redis 6 以下不支持 RESP3 握手，固定用 RESP2
            protocol=2,

            decode_responses=True,

            socket_connect_timeout=1,

            socket_timeout=2
        )

        client.ping()

    except Exception:

        _last_failure = time.monotonic()

        _client = None

        return None

    _client = client

    return _client


def is_enabled():

    return get_client() is not None


# =========================
# 版本号（失效用）
# =========================

def get_version():

    client = get_client()

    if client is None:

        return None

    try:

        version = client.get(VERSION_KEY)

        if version is None:

            client.set(VERSION_KEY, 1)

            version = "1"

    except Exception:

        _stats["errors"] += 1

        return None

    return str(version)


def invalidate():
    """
    让所有已缓存的检索结果失效。

    索引重建或文档增删后必须调用，
    否则会命中已经过期的知识库内容。
    """

    client = get_client()

    if client is None:

        return False

    try:

        client.incr(VERSION_KEY)

    except Exception:

        _stats["errors"] += 1

        return False

    _stats["invalidations"] += 1

    return True


# =========================
# key
# =========================

def make_key(query, top_k):

    version = get_version()

    if version is None:

        return None

    digest = hashlib.sha1(
        f"{query}|{top_k}".encode("utf-8")
    ).hexdigest()

    return f"{KEY_PREFIX}:v{version}:{digest}"


# =========================
# 读
# =========================

def get_json(key):

    if key is None:

        return None

    client = get_client()

    if client is None:

        return None

    try:

        raw = client.get(key)

    except Exception:

        _stats["errors"] += 1

        return None

    if raw is None:

        _stats["misses"] += 1

        return None

    try:

        value = json.loads(raw)

    except json.JSONDecodeError:

        # 脏数据直接丢弃，当成未命中
        _stats["errors"] += 1

        return None

    _stats["hits"] += 1

    return value


# =========================
# 写
# =========================

def set_json(key, value, ttl=None):

    if key is None:

        return False

    client = get_client()

    if client is None:

        return False

    try:

        client.set(
            key,
            json.dumps(value, ensure_ascii=False),
            ex=ttl or CACHE_TTL
        )

    except Exception:

        _stats["errors"] += 1

        return False

    _stats["sets"] += 1

    return True


# =========================
# 统计
# =========================

def get_stats():

    total = _stats["hits"] + _stats["misses"]

    return {
        "enabled": is_enabled(),
        "url": REDIS_URL,
        "ttl": CACHE_TTL,
        "key_prefix": KEY_PREFIX,
        "version": get_version(),
        "hits": _stats["hits"],
        "misses": _stats["misses"],
        "sets": _stats["sets"],
        "errors": _stats["errors"],
        "invalidations": _stats["invalidations"],
        "hit_rate": (
            round(_stats["hits"] / total, 4)
            if total
            else 0.0
        )
    }


def reset_stats():

    for key in _stats:

        _stats[key] = 0
