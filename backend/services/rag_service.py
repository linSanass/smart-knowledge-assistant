from database import SessionLocal

from services import cache_service

from services import document_service

from services import file_service

from services import prompts

from services.pdf_service import split_text

from sentence_transformers import (
    SentenceTransformer
)

from openai import OpenAI

from dotenv import load_dotenv

from datetime import (
    datetime,
    timezone
)

import faiss
import numpy as np
import os
import threading


# =========================
# 加载环境变量
# =========================

load_dotenv()


# =========================
# DeepSeek 客户端
# =========================

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


# =========================
# Embedding 模型
# =========================

model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


# =========================
# 全局知识库
# =========================

# 每个元素:
# {
#     "text": 文本块内容,
#     "filename": 来源 PDF,
#     "chunk_index": 在所属 PDF 中的序号,
#     "document_id": documents 表主键
# }
chunks_store = []

# FAISS 向量索引
faiss_index = None


# =========================
# 构建状态与并发控制
# =========================

# 后台构建跑在 Starlette 的线程池里，和 HTTP 请求线程并发访问上面两个全局变量。
# 锁只保护「原子的成对读写」，绝不跨越 model.encode / FAISS 计算，
# 所以不会把并发的构建串行化成一次大阻塞。
_state_lock = threading.RLock()

_build_state = {
    "building": False,
    "started_at": None,
    "finished_at": None,
    "last_result": None,
    "last_error": None,

    # 构建期间又来了一次请求：不打起来，只登记一次「完了再跑一遍」
    "rebuild_requested": False
}


def _now():

    # 和 models.utcnow 保持一致：naive UTC
    return datetime.now(
        timezone.utc
    ).replace(tzinfo=None).isoformat()


def is_building():

    with _state_lock:

        return _build_state["building"]


def _claim_or_request():
    """
    拿到构建权返回 True；已经有构建在跑就把重跑请求记下来并返回 False。

    判断和登记必须在同一次加锁里完成，否则会出现丢更新：
    请求方读到 building=True 后恰好构建方收尾并清空标记，
    请求方再置位就没人消费了，刚上传的 PDF 会悄悄进不了索引。
    """

    with _state_lock:

        if _build_state["building"]:

            _build_state["rebuild_requested"] = True

            return False

        _build_state["building"] = True

        _build_state["started_at"] = _now()

        _build_state["finished_at"] = None

        _build_state["last_error"] = None

        _build_state["rebuild_requested"] = False

        return True


def run_build_task():
    """
    后台构建的统一入口。

    单独抽出来是为了让接口只负责「排队」，不负责「什么时候构建」。
    构建期间收到的新请求会在本轮结束后补跑一次，不丢上传。
    """

    if not _claim_or_request():

        return

    try:

        while True:

            try:

                result = build_vector_store()

            except Exception as error:

                # 系统性失败（不是单个 PDF 坏）：记录，不再重试
                with _state_lock:

                    _build_state["last_error"] = str(error)[:1000]

                    _build_state["last_result"] = None

                break

            with _state_lock:

                _build_state["last_result"] = result

                _build_state["last_error"] = None

                if not _build_state["rebuild_requested"]:

                    break

                _build_state["rebuild_requested"] = False

    finally:

        # 必须放 finally：否则一次崩溃会让 building 永远为真，
        # 之后所有构建都被 409 挡住
        with _state_lock:

            _build_state["building"] = False

            _build_state["finished_at"] = _now()

        # 构建崩在中途时会有文档卡在 processing，退回 pending 以便重试。
        # 构建成功时这里通常是空操作（都已经是 ready / failed）
        _cleanup_processing()


def _cleanup_processing():

    try:

        db = SessionLocal()

    except Exception:

        return

    try:

        document_service.reset_processing(db)

    except Exception:

        # 收尾失败不应该盖掉本次构建的结果
        pass

    finally:

        db.close()


# =========================
# 构建向量数据库
# =========================

def build_vector_store():
    """
    对 uploads 下所有已登记的文件与笔记建立统一索引。

    构建过程中先写入局部变量，全部成功后再替换全局索引，
    避免中途失败把旧索引破坏掉。
    """

    global chunks_store
    global faiss_index

    db = SessionLocal()

    try:

        # 0. 补登记 uploads 里遗漏的文件
        document_service.sync_documents(db)

        documents = document_service.list_documents(db)

        if not documents:

            # 已经没有文档了，必须清空旧索引，
            # 否则被删除文件的 chunk 还会被检索到
            with _state_lock:

                chunks_store = []
                faiss_index = None

            cache_service.invalidate()

            return {
                "message": "没有可用的文件，请先上传",
                "chunk_count": 0,
                "documents": 0
            }

        # 先把待处理的文档标成 processing，前端就能显示「处理中」；
        # 下面逐个解析完会立刻改成 ready / failed
        document_service.mark_processing(db, documents)

        new_chunks = []

        failed = []

        # =========================
        # 1. 逐个取文本 + 切分
        # =========================

        for document in documents:

            try:

                # 笔记的正文直接取 content，PDF 才去读文件。
                #
                # 这是整个索引流程里唯一为「笔记」分叉的地方：
                # 切分、embedding、FAISS、检索都不需要知道内容来自哪种来源，
                # chunk 里照旧写 filename（笔记即标题）与 document_id，
                # 所以 serialize_source 的字段也一个没动
                if document_service.is_note(document):

                    # 标题一起进索引：用户按标题里的关键词搜索时应该能找到，
                    # 否则「Unity Addressables」这种标题只能靠正文命中
                    text = f"{document.filename}\n\n{document.content or ''}"

                else:

                    # 按扩展名取文本：PDF 走 pypdf，
                    # TXT / Markdown 按文本读。格式判断收在 file_service 里，
                    # 切分、embedding、FAISS、检索都不关心是哪种文件
                    text = file_service.extract_text(
                        document.file_path
                    )

                if not text or not text.strip():

                    document_service.mark_failed(
                        db,
                        document,
                        "内容为空"
                    )

                    failed.append(document.filename)

                    continue

                chunks = split_text(text)

                for index, chunk in enumerate(chunks):

                    new_chunks.append({
                        "text": chunk,
                        "filename": document.filename,
                        "chunk_index": index,
                        "document_id": document.id
                    })

                document_service.mark_ready(
                    db,
                    document,
                    len(chunks)
                )

            except Exception as error:

                # 单个文件坏掉不影响其它文件
                document_service.mark_failed(
                    db,
                    document,
                    error
                )

                failed.append(document.filename)

        # 所有文件都失败：同样要清空旧索引，避免检索到已失效内容
        if not new_chunks:

            with _state_lock:

                chunks_store = []
                faiss_index = None

            cache_service.invalidate()

            return {
                "message": "所有文件解析失败",
                "chunk_count": 0,
                "documents": len(documents),
                "failed": failed
            }

        # =========================
        # 2. 文本转向量
        # =========================

        embeddings = model.encode(
            [c["text"] for c in new_chunks]
        )

        embeddings = np.array(
            embeddings,
            dtype=np.float32
        )

        # =========================
        # 3. 创建 FAISS 索引
        # =========================

        dimension = embeddings.shape[1]

        new_index = faiss.IndexFlatL2(
            dimension
        )

        # =========================
        # 4. 添加向量
        # =========================

        new_index.add(
            embeddings
        )

        # =========================
        # 5. 替换全局索引
        # =========================

        # 一次成对替换：读方拿到的 chunks_store 和 faiss_index 必须来自同一轮构建
        with _state_lock:

            chunks_store = new_chunks

            faiss_index = new_index

        # 索引变了，之前缓存的检索结果全部失效
        cache_service.invalidate()

        return {
            "message": "知识库构建成功",
            "chunk_count": len(new_chunks),
            "documents": len(documents),
            "failed": failed
        }

    finally:

        db.close()


# =========================
# 索引状态
# =========================

def get_index_status():
    """
    索引状态，前端轮询这个接口。

    built / chunk_count / documents 永远是最后一批成功构建的结果，
    构建过程中的中间态放在 building 和 last_* 里。
    """

    with _state_lock:

        index, store = faiss_index, chunks_store

        state = dict(_build_state)

    return {
        "built": index is not None,
        "chunk_count": len(store),
        "documents": len({
            c["document_id"]
            for c in store
        }),
        "building": state["building"],
        "started_at": state["started_at"],
        "finished_at": state["finished_at"],
        "last_result": state["last_result"],
        "last_error": state["last_error"]
    }


# =========================
# 搜索知识库
# =========================

def search_chunks(query, top_k=3):

    # 成对取快照：构建线程是分两步替换全局变量的，
    # 不加锁可能读到「新的 chunks_store + 旧的 faiss_index」，
    # 那会把向量检索结果配上错误的原文，来源引用就错了。
    with _state_lock:

        index, store = faiss_index, chunks_store

    # 没有构建知识库
    if index is None:

        return []

    # 没有文本块
    if not store:

        return []

    # =========================
    # 1. 问题转向量
    # =========================

    query_embedding = model.encode(
        [query]
    )

    query_embedding = np.array(
        query_embedding,
        dtype=np.float32
    )

    # =========================
    # 2. FAISS 搜索
    # =========================

    distances, indices = index.search(
        query_embedding,
        min(top_k, len(store))
    )

    # =========================
    # 3. 组装结果（带来源信息）
    # =========================

    results = []

    for position, idx in enumerate(indices[0]):

        if idx >= 0 and idx < len(store):

            chunk = store[idx]

            results.append({
                "filename": chunk["filename"],
                "chunk_index": chunk["chunk_index"],
                "document_id": chunk["document_id"],
                "chunk": chunk["text"],
                "distance": float(distances[0][position])
            })

    return results


# =========================
# 来源序列化
# =========================

def serialize_source(item):
    """
    RAG 引用来源的统一结构。

    前端和 API 都依赖这几个字段：
        filename     来源 PDF 文件名
        chunk_index  在所属 PDF 中的块序号
        chunk        命中的原文
        document_id  对应 documents 表主键
    """

    return {
        "document_id": item.get("document_id"),
        "filename": item.get("filename"),
        "chunk_index": item.get("chunk_index"),
        "chunk": item.get("chunk")
    }


# =========================
# 拼接上下文
# =========================

def build_context(results):
    """
    把检索结果拼成带来源标记的上下文，
    让模型知道每段内容来自哪个文件。
    """

    blocks = []

    for index, item in enumerate(results, start=1):

        blocks.append(
            f"[片段{index}] 来源: {item['filename']} "
            f"(第{item['chunk_index'] + 1}块)\n"
            f"{item['chunk']}"
        )

    return "\n\n".join(blocks)


# =========================
# RAG 问答
# =========================

def rag_chat(question: str):

    # =========================
    # 1. 检查知识库
    # =========================

    if faiss_index is None:

        return {
            "answer": prompts.EMPTY_KB_ANSWER,
            "sources": []
        }

    if not chunks_store:

        return {
            "answer": prompts.EMPTY_KB_ANSWER,
            "sources": []
        }

    # =========================
    # 2. 搜索相关内容
    # =========================

    docs = search_chunks(
        question
    )

    # 没有搜索结果
    if not docs:

        return {
            "answer": prompts.NO_CONTEXT_ANSWER,
            "sources": []
        }

    # =========================
    # 3. 拼接上下文
    # =========================

    context = build_context(docs)

    # =========================
    # 4. 构造 Prompt
    #    System Instruction / Retrieved Context / User Question
    # =========================

    messages = prompts.build_rag_messages(
        context,
        question
    )

    # =========================
    # 5. 调用 DeepSeek
    # =========================

    response = client.chat.completions.create(

        model="deepseek-chat",

        messages=messages
    )

    # =========================
    # 6. 获取回答
    # =========================

    answer = response.choices[0].message.content

    # =========================
    # 7. 返回给前端（带来源）
    # =========================

    return {
        "answer": answer,
        "sources": [
            serialize_source(item)
            for item in docs
        ]
    }
