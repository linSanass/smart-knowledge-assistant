from services.pdf_service import read_pdf

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
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

# 保存文本块
chunks_store = []

# FAISS 向量索引
faiss_index = None


# =========================
# 构建向量数据库
# =========================

def build_vector_store():

    global chunks_store
    global faiss_index

    # 1. 读取 PDF
    text = read_pdf()

    # 如果读取 PDF 出错
    if isinstance(text, dict):

        return text

    # 如果 PDF 没有内容
    if not text or not text.strip():

        return {
            "message": "PDF 内容为空",
            "chunk_count": 0
        }

    # =========================
    # 2. 文本切分
    # =========================

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )

    chunks = splitter.split_text(text)

    # 保存文本块
    chunks_store = chunks

    # =========================
    # 3. 文本转向量
    # =========================

    embeddings = model.encode(
        chunks
    )

    embeddings = np.array(
        embeddings,
        dtype=np.float32
    )

    # =========================
    # 4. 创建 FAISS 索引
    # =========================

    dimension = embeddings.shape[1]

    faiss_index = faiss.IndexFlatL2(
        dimension
    )

    # =========================
    # 5. 添加向量
    # =========================

    faiss_index.add(
        embeddings
    )

    return {
        "message": "知识库构建成功",
        "chunk_count": len(chunks)
    }


# =========================
# 搜索知识库
# =========================

def search_chunks(query):

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
        min(3, len(chunks_store))
    )

    # =========================
    # 3. 获取文本
    # =========================

    results = []

    for idx in indices[0]:

        if idx >= 0 and idx < len(chunks_store):

            results.append(
                chunks_store[idx]
            )

    return results


# =========================
# RAG 问答
# =========================

def rag_chat(question: str):

    # =========================
    # 1. 检查知识库
    # =========================

    if faiss_index is None:

        return {
            "answer": "知识库为空，请先执行 build-rag",
            "sources": []
        }

    if not chunks_store:

        return {
            "answer": "知识库为空，请先执行 build-rag",
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
            "answer": "没有找到与问题相关的知识库内容。",
            "sources": []
        }

    # =========================
    # 3. 拼接上下文
    # =========================

    context = "\n\n".join(
        docs
    )

    # =========================
    # 4. 构造 Prompt
    # =========================

    prompt = f"""
你是一名知识库助手。

请严格根据下面提供的知识库内容回答问题。

如果知识库中没有相关信息，请明确告诉用户：
"知识库中没有找到相关信息。"

不要使用知识库之外的信息进行推测。

====================
知识库内容
====================

{context}

====================
用户问题
====================

{question}

====================
回答要求
====================

请用简洁、准确的中文回答。
"""

    # =========================
    # 5. 调用 DeepSeek
    # =========================

    response = client.chat.completions.create(

        model="deepseek-chat",

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    # =========================
    # 6. 获取回答
    # =========================

    answer = response.choices[0].message.content

    # =========================
    # 7. 返回给前端
    # =========================

    return {
        "answer": answer,
        "sources": docs
    }