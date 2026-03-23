"""
ai.py  —  Groq proxy for Element (flat structure)
Key lives only in Railway env vars: GROQ_API_KEY
"""
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from security import get_current_user

router = APIRouter(prefix="/ai", tags=["AI"])

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"


class AIRequest(BaseModel):
    system: str
    prompt: str
    max_tokens: int = 600


class AIResponse(BaseModel):
    result: str


@router.post("/generate", response_model=AIResponse)
async def generate(
    body: AIRequest,
    current_user=Depends(get_current_user),
):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="AI service not configured.")

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
