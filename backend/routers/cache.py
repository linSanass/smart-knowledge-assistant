from fastapi import APIRouter

from services import cache_service


router = APIRouter(
    prefix="/cache",
    tags=["cache"]
)


@router.get("/stats")
def stats():
    """
    缓存状态：是否可用、TTL、命中/未命中次数、命中率。
    """

    return cache_service.get_stats()


@router.post("/clear")
def clear():
    """
    让所有已缓存的检索结果失效。

    通过自增版本号实现，不需要遍历删除 key。
    """

    invalidated = cache_service.invalidate()

    cache_service.reset_stats()

    return {
        "message": (
            "缓存已失效"
            if invalidated
            else "Redis 不可用，缓存本来就未生效"
        ),
        "invalidated": invalidated,
        "stats": cache_service.get_stats()
    }
