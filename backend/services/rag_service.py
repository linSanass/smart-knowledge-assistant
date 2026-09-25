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

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

chunks_store = []

faiss_index = None


def build_vector_store():

    global chunks_store
    global faiss_index

    text = read_pdf()

    if isinstance(text, dict):
        return text

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )

    chunks = splitter.split_text(text)

    chunks_store = chunks

    embeddings = model.encode(chunks)

    dimension = embeddings.shape[1]

    faiss_index = faiss.IndexFlatL2(
        dimension
    )

    faiss_index.add(
        np.array(
            embeddings,
            dtype=np.float32
        )
    )

    return {
        "chunk_count": len(chunks)
    }


def search_chunks(query):

    global faiss_index
    global chunks_store

    if faiss_index is None:
        return []

    query_embedding = model.encode(
        [query]
    )

    distances, indices = faiss_index.search(
        np.array(
            query_embedding,
            dtype=np.float32
        ),
        3
    )

    results = []

    for idx in indices[0]:

        if idx < len(chunks_store):

            results.append(
                chunks_store[idx]
            )

    return results


def rag_chat(query):

    chunks = search_chunks(query)

    if len(chunks) == 0:

        return "知识库为空，请先执行 build-rag"

    context = "\n\n".join(chunks)

    prompt = f"""
你是一名知识库问答助手。

请严格依据知识库内容回答问题。

如果知识库没有相关内容，
请明确说明：

知识库中未找到相关信息。

知识库内容：

{context}

用户问题：

{query}
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response.choices[0].message.content