from services.pdf_service import read_pdf

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)

from sentence_transformers import (
    SentenceTransformer
)

import faiss
import numpy as np

model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

chunks_store = []

faiss_index = None

def build_vector_store():

    global chunks_store
    global faiss_index

    text = read_pdf()

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