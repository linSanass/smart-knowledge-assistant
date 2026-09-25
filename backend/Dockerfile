# 3.12 而不是本机的 3.14：
# faiss-cpu / sentence-transformers / numpy 在 3.12 上的 wheel 覆盖最稳
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

# HuggingFace 在国内直连不通。默认走官方地址（配了代理就能通），
# 需要时可覆盖：docker compose build --build-arg HF_ENDPOINT=https://hf-mirror.com
ARG HF_ENDPOINT=https://huggingface.co
ENV HF_ENDPOINT=${HF_ENDPOINT}

COPY requirements.txt .

# 先单独装 CPU 版 torch。
# sentence-transformers 的依赖默认会拉 CUDA 版 torch，连带几 GB 的 nvidia 库；
# 本项目是 faiss-cpu + CPU 推理，那些库一点用不上（镜像会从 ~1.4GB 涨到 ~10GB）。
# 先装好 CPU 版，后面装 requirements 时 pip 发现 torch 已满足，就不会再装 CUDA 版
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

# 构建阶段就把 embedding 模型下好。
# 否则首次启动会在 import 阶段拉模型，compose up 看起来像卡死了
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

EXPOSE 8000

# 必须单进程：FAISS 索引和构建状态都是进程内内存态，
# 多 worker 会各持一份索引，检索结果和构建状态都会对不上
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
