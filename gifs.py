"""
gifs.py  —  Giphy proxy for Element (flat structure)
Key lives only in Railway env vars: GIPHY_API_KEY
"""
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from auth import get_current_user

router = APIRouter(prefix="/gifs", tags=["GIFs"])
GIPHY_BASE = "https://api.giphy.com/v1/gifs"


@router.get("/trending")
async def trending(
    limit: int = Query(24, le=50),
    current_user=Depends(get_current_user),
):
    key = os.getenv("GIPHY_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="GIF service not configured.")
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(
            f"{GIPHY_BASE}/trending",
            params={"api_key": key, "limit": limit, "rating": "g"},
        )
    if res.status_code != 200:
        raise HTTPException(status_code=502, detail="GIF service error.")
    return res.json()


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(24, le=50),
    current_user=Depends(get_current_user),
):
    key = os.getenv("GIPHY_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="GIF service not configured.")
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(
            f"{GIPHY_BASE}/search",
            params={"api_key": key, "q": q, "limit": limit, "rating": "g"},
        )
    if res.status_code != 200:
        raise HTTPException(status_code=502, detail="GIF service error.")
    return res.json()
