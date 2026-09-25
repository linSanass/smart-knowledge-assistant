from services.pdf_service import read_pdf

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)

vector_store = None


def build_vector_store():

    global vector_store

    text = read_pdf()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )

    chunks = splitter.split_text(text)

    vector_store = chunks

    return {
        "chunk_count": len(chunks)
    }