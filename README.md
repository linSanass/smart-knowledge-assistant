# Smart Knowledge Assistant

一个可运行、可解释的 AI 全栈项目：上传 PDF / TXT / Markdown 构建个人知识库，然后基于 RAG 问答，
并支持 Function Calling 与分步 Agent。

不只是「调通一个接口」：检索结果带来源引用、会话与消息落库、知识库构建异步化、
检索结果带 Redis 缓存、四个服务可以一条命令容器化启动，CI 上真跑测试。

---

## 目录

- [功能列表](#功能列表)
- [技术栈](#技术栈)
- [项目架构](#项目架构)
- [环境要求](#环境要求)
- [环境变量](#环境变量)
- [MySQL 配置](#mysql-配置)
- [Redis 配置](#redis-配置)
- [本地启动](#本地启动)
- [Docker 启动](#docker-启动)
- [API 简介](#api-简介)
- [测试](#测试)
- [常见问题](#常见问题)

---

## 功能列表

### 对话

- **多会话**：新建 / 切换 / 删除，会话列表按更新时间排序
- **聊天历史**：消息持久化到 MySQL，切换会话可还原
- **四种模式**，同一个接口按 `mode` 切换：
  - `chat` —— 普通对话，带多角色 System Prompt
  - `rag` —— 知识库问答，返回引用来源
  - `tools` —— Function Calling，单轮工具调用
  - `agent` —— 分步 Agent，多步调用工具直到得出答案

### 知识库（RAG）

- 支持 **PDF / TXT / Markdown** 三种格式，统一进同一个知识库
  - PDF 校验扩展名 **和** 文件头，拦截改了后缀的假 PDF
  - TXT / Markdown 没有魔数，用「是否含 NUL 字节」识别伪装成文本的二进制文件
  - 文本按 UTF-8 → GBK 的顺序尝试解码，中文环境的旧 TXT 也能读
- 多文档统一索引，支持列表 / 删除
- **每个 chunk 可回溯来源**：命中结果带 `filename` + `chunk_index` + `document_id`
- **异步构建**：上传后立即返回 202，解析 / 切分 / embedding / FAISS 全部在后台跑，
  前端轮询状态；构建期间再次触发返回 409，不会两次构建同时改索引
- 单个 PDF 损坏不影响其它文档，失败原因写回该文档的 `status` 与 `error`
- **手写知识**：可以直接新建 / 编辑一条知识（标题 + 内容），
  保存后和 PDF 一样进入检索索引，回答里同样能作为来源被引用
- **统一列表**：PDF 与手写知识在侧栏同一个列表里展示（📄 / 📝 区分），
  点击可看详情（文件名、上传时间、文件大小、状态），删除带确认

### 工具与 Agent

内置三个工具，注册表统一管理 schema：

| 工具 | 说明 |
| --- | --- |
| `calculator` | 四则运算与常用数学函数。**用 AST 白名单求值，不用 `eval`**，拒绝 `__import__` / `open` / lambda / 推导式等 |
| `knowledge_search` | 检索知识库（带 Redis 缓存） |
| `current_time` | 当前时间，支持指定时区 |

工具调用轨迹（`tool_calls`）会随消息一起持久化，Agent 模式额外带 `step` 序号。

### 其他

- **Redis 缓存**：只缓存 `knowledge_search` 的检索结果，带 TTL；
  用版本号做失效（重建索引时自增，旧 key 自然读不到）；
  **Redis 不可用时自动降级**，不影响检索本身
- **Docker**：`docker compose up` 起 mysql / redis / backend / frontend 四个服务
- **CI**：push 与 PR 触发，跑后端依赖安装、Python 检查、三个不依赖外部 API 的测试，以及前端 lint 与构建

---

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React 19、Vite 8、oxlint（无状态库、无路由，原生 `useState` / `useRef`） |
| 后端 | Python 3.12、FastAPI 0.141、Uvicorn、Pydantic 2 |
| 大模型 | DeepSeek（`deepseek-chat`），OpenAI 兼容 SDK |
| 向量检索 | FAISS（`IndexFlatL2`）、SentenceTransformer `all-MiniLM-L6-v2` |
| PDF | pypdf、langchain-text-splitters |
| 数据库 | MySQL 8.4 + SQLAlchemy 2 + PyMySQL |
| 缓存 | Redis 7 / redis-py 8 |
| 部署 | Docker、Docker Compose |
| CI | GitHub Actions |

---

## 项目架构

```text
React (5173)
  │  fetch → http://127.0.0.1:8000
  ▼
FastAPI (8000)
  ├── routers/           路由层，只做参数校验与响应组装
  │     conversations  documents  tools  agent  cache
  ├── services/          业务层
  │     ├─ conversation_service   会话与消息，四种模式分发
  │     ├─ chat_service           普通对话 + 多角色 System Prompt
  │     ├─ rag_service            PDF → chunk → embedding → FAISS → 检索
  │     ├─ function_calling_service / agent_service   工具调用循环
  │     ├─ tools                  calculator / knowledge_search / current_time
  │     ├─ document_service       文档登记、状态流转
  │     ├─ pdf_service            PDF 读写与切分
  │     ├─ prompts                RAG Prompt 拼装
  │     └─ cache_service          Redis 缓存与降级
  ├── database.py        Engine / Session / 轻量迁移
  └── models.py          documents / conversations / chat_messages
  ▼
MySQL（会话、消息、文档）      Redis（检索缓存）
```

### RAG 链路

```text
PDF 上传 → 落盘 + 登记 documents 表（status=pending）
        → 后台任务：解析 → 切分 → embedding → FAISS
        → 成功后原子替换索引，并让 Redis 缓存失效
        → 检索：问题向量化 → FAISS 近邻 → 拼上下文 → DeepSeek → 带来源回答
```

索引只在全部构建成功后**一次性替换**，中途失败不会破坏旧索引。

### 异步构建的状态机

```text
pending ──构建开始──> processing ──成功──> ready
                            └──失败──> failed（error 记录原因）
```

构建状态（`building` / `started_at` / `finished_at` / `last_result` / `last_error`）
通过 `GET /documents/status` 暴露，前端轮询它。

---

## 环境要求

| 依赖 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.12+ | Docker 镜像用 3.12 |
| Node.js | 20.19+ / 22.12+ | Vite 8 的要求 |
| MySQL | 8.x | 本地开发或 Docker |
| Redis | 6+ | **可选**。不配也能跑，只是没有缓存 |
| Docker | 29+（含 Compose） | 仅容器化启动时需要 |

还需要一个 **DeepSeek API Key**：[platform.deepseek.com](https://platform.deepseek.com/)

---

## 环境变量

### `backend/.env`（本机直接跑后端时用）

从 `backend/.env.example` 复制：

| 变量 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | 是 | —— | DeepSeek API Key。**不配置服务无法启动**（`rag_service` 在 import 阶段就会构造客户端） |
| `DATABASE_URL` | 是 | —— | SQLAlchemy 连接串，见下 |
| `REDIS_URL` | 否 | `redis://127.0.0.1:6379/0` | 不填或连不上会自动降级为不使用缓存 |
| `CACHE_TTL` | 否 | `300` | 检索结果缓存秒数 |

### 根目录 `.env`（docker compose 时用）

从根目录 `.env.example` 复制。**注意与 `backend/.env` 不是同一个文件**：

| 变量 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `MYSQL_ROOT_PASSWORD` | 否 | `devpassword` | 仅容器内 MySQL 使用；**生产务必覆盖** |

---

## MySQL 配置

数据库名：`smart_ai_assistant`

```text
DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/smart_ai_assistant?charset=utf8mb4
```

首次建库：

```sql
CREATE DATABASE smart_ai_assistant
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

**表结构不用手动建**：应用启动时（FastAPI lifespan）会 `create_all`，
并对比模型与真实表结构自动补列（轻量迁移）。

三张表：

| 表 | 内容 |
| --- | --- |
| `documents` | 知识条目：PDF 与手写知识共用一表，用 `kind` 区分（`pdf` / `note`）。字段有展示名（`filename`，笔记即标题）、路径、正文（`content`，仅笔记）、解析状态与错误 |
| `conversations` | 会话：标题、创建与更新时间 |
| `chat_messages` | 消息：角色、内容、RAG 来源、工具调用轨迹 |

> Docker 启动时不需要手动建库，`MYSQL_DATABASE` 会自动创建。

---

## Redis 配置

```text
REDIS_URL=redis://127.0.0.1:6379/0
```

只缓存 `knowledge_search` 的检索结果，**不迁移 MySQL 的任何数据**。

| 设计 | 说明 |
| --- | --- |
| 缓存键 | `ska:knowledge_search:v<版本>:<query+top_k 的 sha1>` |
| 失效 | 重建索引时版本号自增，旧 key 自然读不到，无需遍历删除 |
| 空结果 | 不缓存 |
| 降级 | 连不上 Redis 时返回「无缓存」，检索照常工作；且 30 秒内不重复重连，避免每次请求都卡在连接超时 |
| 观测 | `GET /cache/stats` 看命中率，`POST /cache/clear` 手动失效 |

---

## 本地启动

### 1. 后端

```bash
cd backend

# 配置环境变量（必须先做，缺 DATABASE_URL 会直接报错退出）
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 和 DATABASE_URL

pip install -r requirements.txt

uvicorn main:app --reload --port 8000
```

启动后：

- 接口文档 <http://127.0.0.1:8000/docs>
- 健康检查 `GET http://127.0.0.1:8000/documents/status`

> 首次启动会下载 embedding 模型（约 90MB），需要等一会。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

打开 <http://localhost:5173>。

> 前端请求地址写在 `frontend/src/api.js` 的 `BASE_URL`，默认 `http://127.0.0.1:8000`。
> 端口如需改动，记得同时改 `backend/main.py` 的 CORS 白名单。

### 3. 开始使用

1. 选一个 PDF，点「上传PDF」
2. 上传后会自动在后台构建知识库，状态行与文档行会显示进度
3. 构建完成后，用「知识库问答」提问，回答下方会列出参考来源

---

## Docker 启动

```bash
docker compose up -d --build
```

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| frontend | <http://localhost:5173> | nginx 托管的前端静态资源 |
| backend | <http://127.0.0.1:8000> | FastAPI |
| mysql | 仅容器网络 | **刻意不映射到宿主机**，避免与本机 MySQL 的 3306 冲突 |
| redis | 仅容器网络 | 同上，避免与 6379 冲突 |

常用命令：

```bash
docker compose ps                 # 看状态与健康检查
docker compose logs -f backend    # 跟后端日志
docker compose down               # 停止（保留数据）
docker compose down -v            # 停止并清空数据库
```

### 两个必须知道的约束

1. **backend 只能单进程**。FAISS 索引与构建状态都是进程内内存态，
   多个 worker 会各持一份索引，检索结果和构建状态都会对不上。
   因此启动命令是 `uvicorn main:app`（不带 `--workers`）。
   如需多副本，得先把索引外置。
2. **uploads 用 bind mount**。PDF 落在宿主机 `backend/uploads/`，
   容器重建不丢；删容器不会删文件。

---

## API 简介

共 25 个端点。完整文档见 <http://127.0.0.1:8000/docs>。

### 会话

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/conversations` | 新建会话 |
| `GET` | `/conversations` | 会话列表 |
| `GET` | `/conversations/{id}` | 会话详情（含消息历史） |
| `DELETE` | `/conversations/{id}` | 删除会话（级联删消息） |
| `POST` | `/conversations/{id}/messages` | 发消息，`mode` 取 `chat` / `rag` / `tools` / `agent` |

### 知识库

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/documents` | 上传文件（`.pdf` / `.txt` / `.md`），**返回 202** 并排队后台构建 |
| `GET` | `/documents` | 知识条目列表：PDF 与手写知识统一返回，带 `kind` / `size` / `status` |
| `GET` | `/documents/status` | 索引状态与构建进度，**前端轮询此接口** |
| `DELETE` | `/documents/{id}` | 删除任意知识条目，返回 `index_rebuild_scheduled` |
| `POST` | `/notes` | 新建手写知识（标题 + 内容），**返回 202** 并排队重建索引 |
| `PUT` | `/notes/{id}` | 编辑手写知识的标题或内容，**返回 202** 并排队重建索引 |
| `GET` | `/build-rag` | 手动触发构建，**202**；构建中重复触发返回 **409** |
| `GET` | `/search?query=` | 直接检索，不经过大模型 |
| `POST` | `/rag-chat` | RAG 问答，返回 `answer` + `sources` |

### 工具与 Agent

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/tools` | 工具列表与 schema |
| `POST` | `/tools/chat` | Function Calling 单轮 |
| `GET` | `/agent/tools` | Agent 可用工具 |
| `POST` | `/agent/chat` | 分步 Agent，返回调用轨迹与步数 |

### 缓存

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/cache/stats` | 命中率、TTL、是否可用、版本号 |
| `POST` | `/cache/clear` | 让所有缓存失效并清零统计 |

### 兼容保留

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/chat` | 旧接口，无历史、无落库 |
| `GET` | `/history` | 内存历史，已被会话功能取代 |
| `POST` | `/clear` | 清空内存历史 |
| `POST` | `/upload` | 旧上传接口，会登记进 documents 表 |
| `GET` | `/read-pdf` · `/split-pdf` | 调试用，查看解析与切分结果 |
| `GET` | `/` | 存活检查 |

### 一个响应示例

```jsonc
// POST /rag-chat  {"question": "HybridCLR 是什么"}
{
  "answer": "根据知识库内容，HybridCLR 是一个支持 AOT 平台的 Unity 热更新方案……",
  "sources": [
    {
      "document_id": 1,
      "filename": "Unity_RAG_Test_Document.pdf",
      "chunk_index": 0,
      "chunk": "Unity Development Knowledge Base\nHybridCLR\n……"
    }
  ]
}
```

---

## 测试

12 个测试文件，都是可直接运行的脚本（不依赖 pytest）：

```bash
cd backend
python tests/test_cache.py
```

> 必须**在 `backend/` 目录下**执行：`pdf_service.UPLOAD_DIR` 是相对路径 `uploads`。

| 文件 | 覆盖 | 需要 DeepSeek |
| --- | --- | --- |
| `test_database.py` | 会话读写、级联删除 | 否 |
| `test_conversations.py` | 多轮上下文、参数校验 | 是 |
| `test_documents.py` | 多文档上传、索引、来源追踪、删除重建 | 是 |
| `test_notes.py` | 手写知识：新建→可检索、编辑→旧内容移出索引、删除、统一列表 | 否 |
| `test_file_formats.py` | PDF / TXT / Markdown 各自上传并检索、GBK 编码、非法格式被拒 | 否 |
| `test_async_documents.py` | 异步构建：非阻塞、409 互斥、不丢上传、崩溃恢复、坏 PDF 隔离 | 否 |
| `test_cache.py` | 缓存命中/失效、TTL、Redis 降级 | 否 |
| `test_tools.py` | 工具单元：calculator 白名单求值、注册表、错误处理 | 否 |
| `test_tools_endpoint.py` | 端到端：模型真的选中正确工具、轨迹可持久化 | 是 |
| `test_agent.py` | 多步工具调用与轨迹持久化 | 是 |
| `test_prompt.py` | RAG Prompt 结构与拒答行为 | 是 |
| `test_sources.py` | 来源字段与可回溯 | 是 |

`test_async_documents.py` 值得一提：因为 `TestClient` 会等后台任务跑完才返回，
它无法观察「请求已返回、处理还没结束」这个窗口。所以它改用
`httpx.ASGITransport` + `threading.Event` 闸门把构建冻住，
用**事件**而不是 `sleep` 来断言构建期间 HTTP 仍可响应。

CI 只跑不依赖 DeepSeek 的五个（`test_cache` / `test_async_documents` / `test_tools` / `test_notes` / `test_file_formats`），
避免每次 push 都消耗 API 额度。端到端部分被拆到单独文件正是为了这个：
`test_tools_endpoint.py` 需要真实的模型调用，所以不进 CI。

---

## 常见问题

### 拉不动 Docker 镜像

`docker pull` 能成功但 `docker compose build` 在拉基础镜像元数据时失败，
是因为 **BuildKit 不继承 daemon 的代理设置**。先手动拉：

```bash
docker pull python:3.12-slim node:22-alpine nginx:alpine mysql:8.4 redis:7-alpine
docker compose build
```

### HuggingFace 连不上

构建镜像时会下载 embedding 模型。网络不通时换镜像源：

```bash
docker compose build --build-arg HF_ENDPOINT=https://hf-mirror.com
```

### 端口被占用

`127.0.0.1:8000` 上的旧进程会**优先于** Docker 的 `0.0.0.0:8000` 接住请求，
让浏览器打到错误的进程。排查：

```bash
netstat -ano | grep ":8000" | grep -i listen
```

### 首次请求很慢

embedding 模型在 `rag_service` import 时加载，冷启动需要几秒到几十秒。
Docker 镜像在构建阶段就下好了模型，所以容器内启动更快。

---

## 一些设计取舍

- **不用 `eval` 做计算器**：`calculator` 走 AST 白名单，只放行数字、四则运算与白名单函数。
- **不引入向量数据库**：文档量级用 FAISS 的 `IndexFlatL2` 足够，也便于讲清楚原理。
- **不用 Agent Framework**：Agent 就是一个带上限的循环，逻辑透明、好调试。
- **缓存不碰 MySQL 数据**：缓存只解决「同一问题重复检索」，不改变数据归属。
- **单进程换简单**：索引放进程内存，牺牲横向扩展换实现简单；
  真要横向扩展，第一步是把索引外置成独立服务。
