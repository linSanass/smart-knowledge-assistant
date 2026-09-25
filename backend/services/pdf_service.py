import os

from pypdf import PdfReader
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)

UPLOAD_DIR = "uploads"


def get_latest_pdf():

    pdf_files = [

        f for f in os.listdir(UPLOAD_DIR)

        if f.endswith(".pdf")
    ]

    if len(pdf_files) == 0:
        return None

    return os.path.join(
        UPLOAD_DIR,
        pdf_files[-1]
    )


def read_pdf():

    pdf_path = get_latest_pdf()

    if pdf_path is None:

        return {
            "error": "没有找到PDF"
        }

    reader = PdfReader(pdf_path)

    text = ""

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:
            text += page_text

    return text


def split_pdf():

    text = read_pdf()

    if isinstance(text, dict):
        return text

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )

    chunks = splitter.split_text(text)

    return {
        "chunk_count": len(chunks),
        "first_chunk": chunks[0]
    }