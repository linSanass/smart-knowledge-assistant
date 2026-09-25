import os

from pypdf import PdfReader
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)

UPLOAD_DIR = "uploads"


def list_pdf_files():

    if not os.path.isdir(UPLOAD_DIR):

        return []

    return sorted(

        f for f in os.listdir(UPLOAD_DIR)

        if f.lower().endswith(".pdf")
    )


def get_latest_pdf():

    pdf_files = list_pdf_files()

    if len(pdf_files) == 0:
        return None

    return os.path.join(
        UPLOAD_DIR,
        pdf_files[-1]
    )


def read_pdf_file(pdf_path):
    """
    读取指定 PDF 的文本。

    解析失败时抛出异常，由调用方决定如何处理，
    这样多文档场景下一个坏文件不会拖垮整个索引。
    """

    reader = PdfReader(pdf_path)

    text = ""

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:
            text += page_text

    return text


def read_pdf():
    """
    读取最近上传的 PDF。

    保留原有行为：出错时返回 {"error": ...} 而不是抛异常。
    """

    pdf_path = get_latest_pdf()

    if pdf_path is None:

        return {
            "error": "没有找到PDF"
        }

    return read_pdf_file(pdf_path)


def split_pdf():

    text = read_pdf()

    if isinstance(text, dict):
        return text

    if not text or not text.strip():

        return {
            "message": "PDF 内容为空",
            "chunk_count": 0
        }

    chunks = split_text(text)

    return {
        "chunk_count": len(chunks),
        "first_chunk": chunks[0]
    }


def split_text(text):
    """
    与原有切分参数保持一致：chunk_size=500, chunk_overlap=100
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )

    return splitter.split_text(text)
