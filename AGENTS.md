# Smart AI Assistant Agent Development Rules

## 1. 项目目标

这是一个用于学习和求职的 AI 全栈项目。

当前技术栈：

* React + Vite
* Python + FastAPI
* DeepSeek API
* FAISS
* SentenceTransformer
* MySQL
* Redis
* Function Calling
* Agent
* Docker
* GitHub Actions

目标：在当前已有项目基础上，逐步完成一个可运行、可解释、结构清晰的 AI Assistant。

---

# 2. 核心原则

### 2.1 增量开发

必须基于当前代码开发。

禁止：

* 重写整个项目
* 删除已有功能
* 无理由大规模重构
* 为了使用某个技术而修改整个架构

优先修改最少的代码完成需求。

---

### 2.2 保护已有 RAG

当前 PDF RAG 已经可以正常工作。

已有能力包括：

```text
PDF Upload
↓
PDF Parsing
↓
Text Chunking
↓
Embedding
↓
FAISS
↓
Similarity Search
↓
DeepSeek
↓
RAG Answer
```

不要重写 RAG。

除非确实存在 Bug 或新功能必须修改，否则保持：

* PDF parsing
* chunking
* embedding
* FAISS
* search_chunks()
* rag_chat()

的现有实现。

---

# 3. 开发顺序

按照以下顺序完成：

```text
1. MySQL
2. Conversation
3. Chat History UI
4. Multi-document Knowledge Base
5. Prompt Engineering
6. RAG Sources
7. Function Calling
8. Agent
9. Redis
10. Async PDF Processing
11. Docker
12. CI/CD
13. README
```

不要跳过核心阶段。

---

# 4. 每个功能的标准开发流程

每个功能严格执行：

```text
读取现有代码
↓
设计最简单可行方案
↓
实现
↓
运行测试
↓
发现 Bug
↓
修复
↓
重新测试
↓
回归测试已有功能
↓
确认通过
↓
Git commit
↓
下一个功能
```

### 特别注意

**代码写完不等于功能完成。**

只有测试通过才能认为功能完成。

不要带着已知核心 Bug 进入下一个阶段。

---

# 5. Git 规则

每个独立功能完成后立即 commit。

格式：

```text
feat: add mysql database
feat: add conversation persistence
feat: add chat history ui
feat: add multi document knowledge base
feat: improve rag prompt
feat: add rag sources
feat: add function calling
feat: add ai agent
feat: add redis cache
feat: add async document processing
feat: add docker deployment
feat: add ci workflow
docs: update project readme
```

不要把多个主要功能合并成一个 commit。

commit 前执行：

```bash
git status
git add .
git commit -m "..."
```

---

# 6. Git 安全

禁止提交：

```text
.env
uploads/
node_modules/
__pycache__/
*.pyc
```

API Key、数据库密码等敏感信息必须通过环境变量配置。

如果没有 `.gitignore`，先创建或完善。

---

# 7. MySQL

数据库：

```text
smart_ai_assistant
```

使用：

```text
SQLAlchemy
PyMySQL
```

建议表：

```text
documents
conversations
chat_messages
```

数据库密码必须通过：

```text
DATABASE_URL
```

配置。

不要写死密码。

---

# 8. Conversation

实现：

```text
POST /conversations
GET /conversations
GET /conversations/{id}
DELETE /conversations/{id}
```

消息保存流程：

```text
User Message
↓
MySQL
↓
LLM / RAG
↓
Assistant Message
↓
MySQL
```

---

# 9. Chat History

React 增加：

```text
New Conversation
Conversation List
Conversation Switch
Delete Conversation
Message History
```

保持现有 UI 风格。

不要为了实现功能重新设计整个前端。

---

# 10. Multi-document Knowledge Base

支持多个 PDF。

至少实现：

* 上传 PDF
* PDF 列表
* 删除 PDF
* 构建索引
* 搜索
* RAG
* PDF 来源追踪

优先继续使用 FAISS。

不要为了多 PDF 强行引入新的向量数据库。

需要保证每个 chunk 能追踪来源 PDF。

---

# 11. Prompt Engineering

RAG Prompt 至少包含：

```text
System Instruction
Retrieved Context
User Question
```

要求：

* 优先根据知识库回答
* 知识库没有答案时明确说明
* 不编造知识库内容
* 保持回答准确
* 保持合理长度

---

# 12. RAG Sources

RAG API 返回：

```json
{
    "answer": "...",
    "sources": []
}
```

source 至少包含：

```text
filename
chunk
```

前端展示参考资料。

---

# 13. Function Calling

至少实现：

```text
calculator
knowledge_search
current_time
```

基本流程：

```text
User
↓
LLM
↓
Tool Selection
↓
Tool
↓
Tool Result
↓
LLM
↓
Final Answer
```

优先使用 DeepSeek 当前 API 支持的 Tool Calling。

不要为了 Function Calling 引入大量无关依赖。

---

# 14. Agent

Function Calling 完成以后实现 Agent。

Agent 至少可以选择：

```text
calculator
knowledge_search
current_time
```

流程：

```text
User
↓
LLM
↓
选择 Tool
↓
执行 Tool
↓
返回 Tool Result
↓
LLM
↓
Final Answer
```

保持简单。

重点是功能真正跑通，而不是堆复杂 Agent Framework。

---

# 15. Redis

在 Agent 完成后增加 Redis。

首先缓存：

```text
knowledge_search
```

实现：

```text
Cache Hit
Cache Miss
TTL
```

不要把所有 MySQL 数据迁移到 Redis。

---

# 16. Async PDF Processing

优先使用：

```text
FastAPI BackgroundTasks
```

流程：

```text
Upload
↓
Background Task
↓
Parse PDF
↓
Chunk
↓
Embedding
↓
FAISS
```

目标是避免 PDF 处理长时间阻塞 HTTP 请求。

不要为了这个功能直接引入 Kafka。

---

# 17. Docker

最后再 Docker 化。

目标：

```text
frontend
backend
mysql
redis
```

使用：

```bash
docker compose up
```

能够启动主要服务。

---

# 18. CI/CD

使用 GitHub Actions。

至少检查：

```text
Backend dependency installation
Python basic check
Frontend npm install
Frontend build
```

不需要为了 CI 强行编写大量测试。

---

# 19. README

最终 README 必须包含：

* 项目介绍
* 技术栈
* 项目架构
* 功能列表
* 环境要求
* 环境变量
* MySQL 配置
* Redis 配置
* 本地启动方法
* Docker 启动方法
* API 简介

---

# 20. 测试规则

每个功能完成后至少测试相关核心路径。

同时进行必要的回归测试。

例如修改 RAG 后必须确认：

```text
PDF Upload
RAG Search
RAG Chat
```

仍然正常。

修改 Chat 后必须确认：

```text
Conversation
Message Save
History
RAG
```

仍然正常。

---

# 21. Bug 处理规则

发现 Bug 时：

1. 先读取错误信息
2. 定位具体原因
3. 修改最小范围代码
4. 重新运行
5. 回归测试

不要通过：

* 删除功能
* 注释掉代码
* 返回假数据
* 硬编码结果
* 绕过错误

来制造“测试通过”。

如果第三方库 API 发生变化：

优先适配当前已安装版本。

不要无理由升级全部依赖。

---

# 22. 环境问题

如果可以通过常规方式解决：

* 安装依赖
* 修改配置
* 修改环境变量
* 修复代码

则自行解决。

只有出现真正无法继续的问题才暂停。

---

# 23. 输出规则

为了减少 Token，每完成一个功能只输出：

```text
功能：
修改：
新增依赖：
测试：
Git Commit：
```

不要重复解释本规则。

完成一个功能后继续下一个。

---

# 24. Agent 执行规则

首次运行：

1. 扫描项目
2. 判断哪些功能已经完成
3. 查看 Git 状态
4. 不覆盖未提交用户修改
5. 从第一个未完成的功能开始执行

如果当前 Git 工作区存在用户未提交修改：

不要覆盖这些修改。

---

# 25. 最终目标

最终项目应该能够：

```text
React
  ↓
FastAPI
  ├── Chat
  ├── Conversation
  ├── RAG
  ├── Knowledge Base
  ├── Function Calling
  ├── Agent
  ├── MySQL
  └── Redis
        ↓
     DeepSeek
```

并且具备：

* PDF 知识库
* RAG
* 多会话
* 聊天历史
* 多文档
* Prompt Engineering
* RAG Source
* Function Calling
* Agent
* Redis Cache
* 异步处理
* Docker
* CI/CD

项目必须保持：

```text
可运行
可维护
可调试
可解释
```

而不是单纯生成大量代码。