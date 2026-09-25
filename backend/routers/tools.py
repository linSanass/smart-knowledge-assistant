from fastapi import APIRouter, HTTPException

from pydantic import BaseModel

from services import function_calling_service as fc

from services import tools

from services.chat_service import roles


router = APIRouter(
    prefix="/tools",
    tags=["tools"]
)


class ToolChatRequest(BaseModel):

    message: str

    # 未知取值会退回 general
    role: str = "general"


@router.get("")
def list_tools():
    """
    列出当前可用的工具。
    """

    return {
        "tools": tools.list_tools()
    }


@router.post("/chat")
def tool_chat(req: ToolChatRequest):

    if not req.message.strip():

        raise HTTPException(
            status_code=400,
            detail="消息不能为空"
        )

    result = fc.run_tools(
        req.message,
        role_prompt=roles.get(req.role, roles["general"])
    )

    return result
