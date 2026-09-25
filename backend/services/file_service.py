"""
知识库文件格式支持。

目前支持 PDF / TXT / Markdown 三种。

判断格式与取文本都收在这里，上层（上传校验、索引、目录登记）
不需要知道具体是哪种格式 —— 加新格式只要改这个文件。
"""

import os

from services import pdf_service


# 允许上传的扩展名
SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".md")

# 直接按文本读取的扩展名；PDF 要走 pypdf
TEXT_EXTENSIONS = (".txt", ".md")

# 依次尝试的编码。
# 中文环境里 GBK 的 TXT 很常见，只试 utf-8 会把它们整份丢进 except
ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")


def extension_of(filename):

    return os.path.splitext(filename or "")[1].lower()


def is_supported(filename):

    return extension_of(filename) in SUPPORTED_EXTENSIONS


def is_text(filename):

    return extension_of(filename) in TEXT_EXTENSIONS


def decode_text(data):
    """
    把字节解码成文本，全部编码都失败时返回 None。

    gb18030 是 gbk 的超集，能覆盖绝大多数中文旧文件
    """

    for encoding in ENCODINGS:

        try:

            return data.decode(encoding)

        except UnicodeDecodeError:

            continue

    return None


def looks_like_binary(content):
    """
    粗略判断是不是二进制内容。

    扩展名可以随便改，而 TXT / Markdown 没有魔数可校验，
    所以用「含 NUL 字节」当判据 —— 正常文本文件里不会出现它
    """

    return b"\x00" in content


def validate(filename, content):
    """
    校验上传内容：通过返回 None，不通过返回给用户看的错误信息。
    """

    extension = extension_of(filename)

    if extension not in SUPPORTED_EXTENSIONS:

        return "只支持 PDF / TXT / Markdown 文件"

    if extension == ".pdf":

        # 拦掉改了后缀的假 PDF
        if not content.startswith(b"%PDF"):

            return "文件内容不是合法的 PDF"

        return None

    if looks_like_binary(content):

        return f"文件内容不是文本，无法作为 {extension} 文件读取"

    if decode_text(content) is None:

        return "文件编码无法识别，请用 UTF-8 或 GBK 保存"

    return None


def read_text_file(file_path):
    """
    读取 TXT / Markdown 的文本。
    """

    with open(file_path, "rb") as handle:

        data = handle.read()

    text = decode_text(data)

    if text is not None:

        return text

    # 兜底：坏字符不该让整份文件进不了知识库，
    # 用 replace 而不是抛异常
    return data.decode("utf-8", errors="replace")


def extract_text(file_path):
    """
    按扩展名取文本。

    这是索引流程里唯一需要知道文件格式的地方：
    切分、embedding、FAISS、检索都不关心内容来自哪种文件。
    """

    if is_text(file_path):

        return read_text_file(file_path)

    return pdf_service.read_pdf_file(file_path)


def list_supported_files():
    """
    列出 uploads 下所有受支持的文件。

    上传目录通过 pdf_service 模块引用而不是直接 import 它的值，
    这样测试替换 UPLOAD_DIR 时这里也跟着变
    """

    upload_dir = pdf_service.UPLOAD_DIR

    if not os.path.isdir(upload_dir):

        return []

    return sorted(
        name
        for name in os.listdir(upload_dir)
        if is_supported(name)
    )
