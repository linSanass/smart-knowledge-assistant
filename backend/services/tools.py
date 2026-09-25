"""
Function Calling 工具集。

包含三个工具：
    calculator        安全计算数学表达式
    knowledge_search  检索知识库
    current_time      获取当前时间

用 DeepSeek 的 OpenAI 兼容 tools 协议描述，
不引入额外依赖。
"""

import ast
import json
import math
import operator

from datetime import datetime, timezone

from zoneinfo import ZoneInfo


# =========================
# 工具定义（发给 LLM）
# =========================

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "计算数学表达式。支持 + - * / // % ** 与 "
                "sqrt/abs/round/min/max/log/sin/cos 等函数，"
                "以及常量 pi 和 e。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "要计算的表达式，例如 (1+2)*3 或 sqrt(16)"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_search",
            "description": (
                "在用户上传的知识库（PDF / TXT / Markdown）中检索相关片段。"
                "当问题涉及知识库内容时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索关键词或问题"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回的片段数量，默认 3"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "current_time",
            "description": "获取当前日期和时间。",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone_name": {
                        "type": "string",
                        "description": (
                            "IANA 时区名，例如 Asia/Shanghai、UTC。"
                            "默认 Asia/Shanghai。"
                        )
                    }
                },
                "required": []
            }
        }
    }
]


# =========================
# calculator
# =========================

_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg
}

_CONSTANTS = {
    "pi": math.pi,
    "e": math.e
}

_FUNCTIONS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "floor": math.floor,
    "ceil": math.ceil
}


def _eval_node(node):

    # 数字
    if isinstance(node, ast.Constant):

        if isinstance(node.value, (int, float)):

            return node.value

        raise ValueError("只支持数字")

    # 二元运算
    if isinstance(node, ast.BinOp):

        op = _BINARY_OPS.get(type(node.op))

        if op is None:

            raise ValueError("不支持的运算符")

        return op(
            _eval_node(node.left),
            _eval_node(node.right)
        )

    # 一元运算
    if isinstance(node, ast.UnaryOp):

        op = _UNARY_OPS.get(type(node.op))

        if op is None:

            raise ValueError("不支持的一元运算符")

        return op(_eval_node(node.operand))

    # 常量名
    if isinstance(node, ast.Name):

        if node.id in _CONSTANTS:

            return _CONSTANTS[node.id]

        raise ValueError(f"未知标识符: {node.id}")

    # 函数调用
    if isinstance(node, ast.Call):

        if not isinstance(node.func, ast.Name):

            raise ValueError("只支持简单函数调用")

        func = _FUNCTIONS.get(node.func.id)

        if func is None:

            raise ValueError(f"不支持的函数: {node.func.id}")

        if node.keywords:

            raise ValueError("不支持关键字参数")

        return func(*[_eval_node(a) for a in node.args])

    raise ValueError(
        f"不支持的语法: {type(node).__name__}"
    )


def calculator(expression):
    """
    计算表达式。

    用 ast 白名单求值，不直接 eval 用户输入。
    """

    if not isinstance(expression, str) or not expression.strip():

        raise ValueError("表达式不能为空")

    # 限制长度，避免构造超长表达式
    if len(expression) > 200:

        raise ValueError("表达式过长")

    try:

        tree = ast.parse(
            expression,
            mode="eval"
        )

    except SyntaxError as error:

        raise ValueError(
            f"表达式语法错误: {error.msg}"
        )

    result = _eval_node(tree.body)

    # 结果格式化：整数不带小数点
    if isinstance(result, float) and result.is_integer():

        result = int(result)

    return result


# =========================
# knowledge_search
# =========================

def knowledge_search(query, top_k=3):

    # 延迟导入，避免 rag_service 启动时加载 embedding 模型
    from services.rag_service import search_chunks

    from services import cache_service

    top_k = max(1, min(int(top_k or 3), 10))

    # =========================
    # 1. 查缓存
    # =========================

    cache_key = cache_service.make_key(query, top_k)

    cached = cache_service.get_json(cache_key)

    if cached is not None:

        # cached 表示这次是缓存命中
        return {**cached, "cached": True}

    # =========================
    # 2. 未命中，真的检索
    # =========================

    results = search_chunks(query, top_k=top_k)

    if not results:

        # 空结果不缓存：构建索引后应该立刻能查到
        return {
            "found": False,
            "message": "知识库为空或没有找到相关内容",
            "results": [],
            "cached": False
        }

    payload = {
        "found": True,
        "results": [
            {
                "filename": item["filename"],
                "chunk_index": item["chunk_index"],
                "chunk": item["chunk"]
            }
            for item in results
        ]
    }

    # =========================
    # 3. 写缓存
    # =========================

    cache_service.set_json(cache_key, payload)

    return {**payload, "cached": False}


# =========================
# current_time
# =========================

def current_time(timezone_name="Asia/Shanghai"):

    name = timezone_name or "Asia/Shanghai"

    try:

        tz = ZoneInfo(name)

    except Exception:

        # 没有 tzdata 或时区名非法时退回 UTC
        tz = timezone.utc

        name = "UTC"

    now = datetime.now(tz)

    return {
        "timezone": name,
        "datetime": now.isoformat(timespec="seconds"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A")
    }


# =========================
# 注册表
# =========================

TOOL_IMPLEMENTATIONS = {
    "calculator": calculator,
    "knowledge_search": knowledge_search,
    "current_time": current_time
}


def get_tool_schemas():

    return TOOL_SCHEMAS


def list_tools():

    return [
        {
            "name": schema["function"]["name"],
            "description": schema["function"]["description"]
        }
        for schema in TOOL_SCHEMAS
    ]


def execute_tool(name, arguments):
    """
    执行工具，统一返回字符串结果。

    无论内部结构如何，最终都要变成文本塞回给 LLM。
    """

    if name not in TOOL_IMPLEMENTATIONS:

        return {
            "ok": False,
            "content": f"未知工具: {name}"
        }

    # arguments 可能是 JSON 字符串，也可能是已经解析好的 dict
    if isinstance(arguments, str):

        try:

            arguments = json.loads(arguments) if arguments.strip() else {}

        except json.JSONDecodeError as error:

            return {
                "ok": False,
                "content": f"参数不是合法 JSON: {error}"
            }

    if not isinstance(arguments, dict):

        arguments = {}

    try:

        result = TOOL_IMPLEMENTATIONS[name](**arguments)

    except TypeError as error:

        return {
            "ok": False,
            "content": f"参数错误: {error}"
        }

    except Exception as error:

        return {
            "ok": False,
            "content": f"{type(error).__name__}: {error}"
        }

    # 结构化结果统一转成紧凑 JSON
    if isinstance(result, (dict, list)):

        content = json.dumps(
            result,
            ensure_ascii=False
        )

    else:

        content = str(result)

    return {
        "ok": True,
        "content": content
    }
