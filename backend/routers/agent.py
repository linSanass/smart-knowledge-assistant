from fastapi import APIRouter, HTTPException

from pydantic import BaseModel

from services import agent_service

from services import tools

from services.chat_service import roles


router = APIRouter(
    prefix="/agent",
    tags=["agent"]
)


class AgentRequest(BaseModel):

    message: str

    # 可选的人设，复用 chat_service 里的角色
    role: str | None = None


@router.get("/tools")
def agent_tools():
    """
    Agent 可以使用的工具。
    """

    return {
        "max_steps": agent_service.MAX_STEPS,
        "tools": tools.list_tools()
    }


@router.post("/chat")
def agent_chat(req: AgentRequest):

    if not req.message.strip():

        raise HTTPException(
            status_code=400,
            detail="消息不能为空"
        )

    return agent_service.run_agent(
        req.message,
        role_prompt=roles.get(req.role) if req.role else None
    )
