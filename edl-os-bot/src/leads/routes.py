"""Email-захват: methodology.html → POST /leads/whitepaper.

Сохраняем email + источник, шлём админу нотификацию в Telegram, возвращаем
200 с прямой ссылкой на PDF.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import insert

from src.core.config import settings
from src.db.models import WhitepaperLead
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/leads", tags=["leads"])

# Rate-limit: 3 заявки / IP / минуту — защита от заливки формы
RATE_LIMIT = 3
RATE_WINDOW_SEC = 60
_ip_buckets: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=RATE_LIMIT))

_PDF_WHITELIST = {
    "founder_os_v1": "/assets/EDL_Founder_OS_v1.pdf",
    "product_ladder_v1": "/assets/EDL_Product_Ladder_v1.pdf",
}


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class WhitepaperIn(BaseModel):
    email: str = Field(..., min_length=4, max_length=254)
    pdf: str = Field(..., min_length=1, max_length=64)
    source: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email")
        return v


def _client_ip(request: Request) -> str:
    # Railway проксирует через X-Forwarded-For
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(f"edl-os::{ip}".encode()).hexdigest()[:32]


def _rate_limited(ip: str) -> bool:
    now = time.time()
    bucket = _ip_buckets[ip]
    while bucket and now - bucket[0] > RATE_WINDOW_SEC:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT:
        return True
    bucket.append(now)
    return False


async def _notify_admin_lead(email: str, pdf: str, source: str | None) -> None:
    from src.main import _ptb_app

    if _ptb_app is None or not settings.admin_chat_id:
        return
    msg = (
        "📄 *Новый лид с whitepaper-формы*\n"
        f"email: `{email}`\n"
        f"pdf: `{pdf}`\n"
        f"источник: {source or '—'}"
    )
    try:
        await _ptb_app.bot.send_message(
            chat_id=settings.admin_chat_id, text=msg, parse_mode="Markdown"
        )
    except Exception:  # noqa: BLE001
        logger.exception("leads: failed to notify admin")


@router.post("/whitepaper")
async def whitepaper(body: WhitepaperIn, request: Request) -> dict[str, str]:
    if body.pdf not in _PDF_WHITELIST:
        raise HTTPException(status_code=400, detail="unknown pdf")

    ip = _client_ip(request)
    if _rate_limited(ip):
        raise HTTPException(status_code=429, detail="rate limited")

    factory = async_session_factory()
    async with factory() as session:
        await session.execute(
            insert(WhitepaperLead).values(
                email=body.email,
                pdf=body.pdf,
                source=body.source,
                user_agent=request.headers.get("user-agent", "")[:300] or None,
                ip_hash=_hash_ip(ip),
            )
        )
        await session.commit()

    await _notify_admin_lead(body.email, body.pdf, body.source)

    return {
        "status": "ok",
        "download_url": _PDF_WHITELIST[body.pdf],
    }
