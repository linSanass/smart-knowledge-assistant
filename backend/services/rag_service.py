from database import SessionLocal

from services import cache_service

from services import document_service

from services import prompts

from services.pdf_service import (
    read_pdf_file,
    split_text
)

from sentence_transformers import (
    SentenceTransformer
)

from openai import OpenAI

from dotenv import load_dotenv

import faiss
import numpy as np
import os


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
# 构建向量数据库
# =========================

def build_vector_store():
    """
    对 uploads 下所有已登记的 PDF 建立统一索引。

    构建过程中先写入局部变量，全部成功后再替换全局索引，
    避免中途失败把旧索引破坏掉。
    """

    global chunks_store
    global faiss_index

    db = SessionLocal()

    try:

        # 0. 补登记 uploads 里遗漏的 PDF
        document_service.sync_documents(db)

        documents = document_service.list_documents(db)

        if not documents:

            # 已经没有文档了，必须清空旧索引，
            # 否则被删除文件的 chunk 还会被检索到
            chunks_store = []
            faiss_index = None

            cache_service.invalidate()

            return {
                "message": "没有可用的 PDF，请先上传",
                "chunk_count": 0,
                "documents": 0
            }

        new_chunks = []

        failed = []

        # =========================
        # 1. 逐个 PDF 解析 + 切分
        # =========================

        for document in documents:

            try:

                text = read_pdf_file(
                    document.file_path
                )

                if not text or not text.strip():

                    document_service.mark_failed(
                        db,
                        document,
                        "PDF 内容为空"
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

            chunks_store = []
            faiss_index = None

            cache_service.invalidate()

            return {
                "message": "所有 PDF 解析失败",
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

    return {
        "built": faiss_index is not None,
        "chunk_count": len(chunks_store),
        "documents": len({
            c["document_id"]
            for c in chunks_store
        })
    }


# =========================
# 搜索知识库
# =========================

def search_chunks(query, top_k=3):

    global faiss_index
    global chunks_store

    # 没有构建知识库
    if faiss_index is None:

        return []

    # 没有文本块
    if not chunks_store:

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

    distances, indices = faiss_index.search(
        query_embedding,
        min(top_k, len(chunks_store))
    )

    # =========================
    # 3. 组装结果（带来源信息）
    # =========================

    results = []

    for position, idx in enumerate(indices[0]):

        if idx >= 0 and idx < len(chunks_store):

            chunk = chunks_store[idx]

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
