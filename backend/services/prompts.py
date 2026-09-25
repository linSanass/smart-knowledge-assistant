"""
集中管理 Prompt 模板。

RAG Prompt 固定包含三部分：
    System Instruction（系统指令）
    Retrieved Context（检索到的知识库内容）
    User Question（用户问题）
"""


# =========================
# System Instruction
# =========================

RAG_SYSTEM_PROMPT = """你是一名严谨的知识库问答助手。

请严格遵守以下规则：

1. 只依据「知识库内容」回答，优先使用知识库中的信息。
2. 如果知识库内容不足以回答问题，直接回答：
   "知识库中没有找到相关信息。"
   不要用知识库以外的知识补充或推测。
3. 不要编造知识库中不存在的事实、数字或结论。
4. 回答准确、条理清晰，长度适中，一般不超过 200 字；
   用户明确要求展开时再详细说明。
5. 引用知识库内容时，用 [片段N] 标注来源。
6. 如果不同片段之间存在冲突，请指出冲突并分别说明来源。"""


# =========================
# 无检索结果时的固定回复
# =========================

NO_CONTEXT_ANSWER = "知识库中没有找到相关信息。"

EMPTY_KB_ANSWER = "知识库为空，请先上传文件并构建知识库。"


# =========================
# Retrieved Context + User Question
# =========================

RAG_USER_TEMPLATE = """====================
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

请严格根据上面的知识库内容回答。如果其中没有答案，
请直接回答"{no_answer}"，不要自行补充。"""


def build_rag_user_prompt(context, question):

    return RAG_USER_TEMPLATE.format(
        context=context,
        question=question,
        no_answer=NO_CONTEXT_ANSWER
    )


def build_rag_messages(context, question):
    """
    组装发给 DeepSeek 的消息列表。
    """

    return [
        {
            "role": "system",
            "content": RAG_SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": build_rag_user_prompt(
                context,
                question
            )
        }
    ]
