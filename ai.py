"""
app/routers/ai.py  —  Groq proxy for Element
Key lives only in Railway env vars. Frontend never sees it.
"""

import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.routers.auth import get_current_user
from app.models import User

router = APIRouter(prefix="/ai", tags=["AI"])

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"


def get_groq_key():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="AI service not configured.")
    return key


class AIRequest(BaseModel):
    system: str
    prompt: str
    max_tokens: int = 600


class AIResponse(BaseModel):
    result: str


@router.post("/generate", response_model=AIResponse)
async def generate(
    body: AIRequest,
    current_user: User = Depends(get_current_user),
):
    """Proxy Groq — key never leaves the server."""
    key = get_groq_key()

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "max_tokens": body.max_tokens,
                "messages": [
                    {"role": "system", "content": body.system},
                    {"role": "user", "content": body.prompt},
                ],
            },
        )

    if res.status_code != 200:
        raise HTTPException(status_code=502, detail="AI service error.")

    data = res.json()
    result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return AIResponse(result=result)
