"""
app/routers/ai.py  ─  AI-powered endpoints for Element
────────────────────────────────────────────────────────
Endpoints:
  POST /ai/write-post      → generate post content from a prompt
  POST /ai/complete-profile → generate headline + bio from user data
  POST /ai/suggest-tags     → suggest hashtags for a post

Requires:  pip install anthropic
Set env:   ANTHROPIC_API_KEY=sk-ant-...
"""

import json
import os

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/ai", tags=["AI"])

# ─── Anthropic client (lazy so missing key just raises on use) ────
def get_claude():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not configured. Set ANTHROPIC_API_KEY.",
        )
    return anthropic.Anthropic(api_key=key)


# ─── Request / Response schemas ───────────────────────────────────

class WritePostRequest(BaseModel):
    prompt: str
    tone: str = "professional"        # professional | casual | inspirational
    language: str = "English"         # English | العربية | Français
    max_words: int = 200


class WritePostResponse(BaseModel):
    content: str
    suggested_tags: list[str]
    suggested_feeling: str | None


class CompleteProfileRequest(BaseModel):
    role: str = ""
    industry: str = ""
    skills: str = ""
    years_experience: str = ""
    extra_context: str = ""


class CompleteProfileResponse(BaseModel):
    headline: str
    bio: str


class SuggestTagsRequest(BaseModel):
    content: str


class SuggestTagsResponse(BaseModel):
    tags: list[str]


# ─── Helpers ─────────────────────────────────────────────────────

AVAILABLE_TAGS = [
    "Education", "Finance", "Law", "Technology", "Health", "Business",
    "Science", "Arts", "Sports", "Politics", "Environment", "Career",
    "Startup", "Marketing", "Leadership", "Culture", "Travel", "Food",
    "Design", "Philosophy",
]

FEELINGS = [
    "Inspiring", "Joy", "Encouraged", "Love", "Faith", "Motivated",
    "Amazed", "Sad", "Angry", "Thoughtful", "Celebrating", "Grateful",
]


# ─── Routes ──────────────────────────────────────────────────────

@router.post("/write-post", response_model=WritePostResponse)
async def write_post(
    body: WritePostRequest,
    current_user: User = Depends(get_current_user),
):
    """Premium: generate a full post from a user prompt."""
    if not current_user.is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI Write is a Premium feature. Upgrade to access it.",
        )

    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    claude = get_claude()

    system = (
        "You are a professional social media content writer for Element, "
        "a LinkedIn-style network popular in Morocco and the MENA region. "
        "Write engaging, authentic posts. No excessive emojis. "
        f"Language: {body.language}. Tone: {body.tone}. "
        f"Target length: ~{body.max_words} words."
    )

    prompt = (
        f"Write a compelling professional post based on this idea:\n\n"
        f"\"{body.prompt}\"\n\n"
        f"Then choose up to 3 relevant tags from this list: {AVAILABLE_TAGS}\n"
        f"Then choose one feeling that fits: {FEELINGS}\n\n"
        f"Return ONLY valid JSON:\n"
        '{"content": "the post text", "tags": ["tag1", "tag2"], "feeling": "feeling name"}'
    )

    try:
        message = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())
        return WritePostResponse(
            content=parsed.get("content", ""),
            suggested_tags=parsed.get("tags", [])[:3],
            suggested_feeling=parsed.get("feeling"),
        )
    except json.JSONDecodeError:
        # Claude returned plain text — wrap it
        return WritePostResponse(
            content=raw,
            suggested_tags=[],
            suggested_feeling=None,
        )
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"AI error: {str(e)}")


@router.post("/complete-profile", response_model=CompleteProfileResponse)
async def complete_profile(
    body: CompleteProfileRequest,
    current_user: User = Depends(get_current_user),
):
    """Premium: generate a professional headline and bio."""
    if not current_user.is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI Profile is a Premium feature.",
        )

    claude = get_claude()

    context_parts = []
    if current_user.full_name:
        context_parts.append(f"Name: {current_user.full_name}")
    if body.role:
        context_parts.append(f"Role: {body.role}")
    if body.industry:
        context_parts.append(f"Industry: {body.industry}")
    if body.skills:
        context_parts.append(f"Skills: {body.skills}")
    if body.years_experience:
        context_parts.append(f"Experience: {body.years_experience}")
    if body.extra_context:
        context_parts.append(f"Additional info: {body.extra_context}")

    prompt = (
        "You are a professional LinkedIn profile writer. "
        "Generate a compelling headline (max 15 words) and bio (3-4 sentences) "
        "for this professional:\n\n"
        + "\n".join(context_parts)
        + "\n\nReturn ONLY valid JSON:\n"
        '{"headline": "...", "bio": "..."}'
    )

    try:
        message = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())
        return CompleteProfileResponse(
            headline=parsed.get("headline", ""),
            bio=parsed.get("bio", ""),
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Could not parse AI response.")
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"AI error: {str(e)}")


@router.post("/suggest-tags", response_model=SuggestTagsResponse)
async def suggest_tags(
    body: SuggestTagsRequest,
    current_user: User = Depends(get_current_user),
):
    """Suggest relevant tags for a post (available to all users)."""
    if not body.content.strip():
        return SuggestTagsResponse(tags=[])

    claude = get_claude()

    prompt = (
        f"Read this social media post and suggest the most relevant tags "
        f"from this list: {AVAILABLE_TAGS}\n\n"
        f"Post:\n{body.content[:500]}\n\n"
        f"Return ONLY a JSON array of up to 4 tags: [\"tag1\", \"tag2\"]"
    )

    try:
        message = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        tags = json.loads(raw.strip())
        valid = [t for t in tags if t in AVAILABLE_TAGS][:4]
        return SuggestTagsResponse(tags=valid)
    except Exception:
        return SuggestTagsResponse(tags=[])
