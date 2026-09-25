from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def root():
    return {
        "message": "Smart Knowledge Assistant Backend Running"
    }

@app.post("/chat")
def chat(req: ChatRequest):
    return {
        "answer": f"你刚刚说的是：{req.message}"
    }