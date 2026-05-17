"""Web chat widget endpoints (для bot-widget.js на elephantdreams.ru).

Архитектура:
- POST /widget/message — принимает сообщение, ставит фоновую задачу на LLM,
  сразу возвращает 202. Ответ улетает в SSE-канал.
- GET  /widget/stream/{session_id} — Server-Sent Events: бот пушит ответы
  в asyncio.Queue, клиент слушает text/event-stream.

Хранение состояния:
- In-memory pubsub (`_queues`, `_history`) — пока бот живёт в одном инстансе
  на Railway, этого достаточно. При горизонтальном масштабировании заменить
  на Redis pub/sub.
- История диалога в памяти, лимит MAX_HISTORY на сессию.
- Email-leads и эскалации к менеджеру логируются в Event.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import insert

from src.core.config import settings
from src.core.llm import reply as llm_reply
from src.db.models import Event
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/widget", tags=["widget"])


# ── In-memory state ─────────────────────────────────────────────────────────
MAX_HISTORY = 10
MAX_MESSAGE_LEN = 2000
SESSION_TTL_SEC = 60 * 60  # 1 час неактивности → чистим
SSE_HEARTBEAT_SEC = 15
RATE_LIMIT_PER_MIN = 12  # 12 сообщений / мин с одной сессии

_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
_history: dict[str, list[dict[str, str]]] = defaultdict(list)
_last_seen: dict[str, float] = {}
_rate_buckets: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=RATE_LIMIT_PER_MIN))

_SESSION_RE = re.compile(r"^w_[a-z0-9]{4,40}$")


def _valid_session(sid: str) -> bool:
    return bool(_SESSION_RE.match(sid))


def _get_queue(session_id: str) -> asyncio.Queue[dict[str, Any]]:
    q = _queues.get(session_id)
    if q is None:
        q = asyncio.Queue(maxsize=32)
        _queues[session_id] = q
    return q


def _gc_expired_sessions() -> None:
    """Удаляем сессии без активности > TTL — освобождаем память."""
    now = time.time()
    stale = [sid for sid, ts in _last_seen.items() if now - ts > SESSION_TTL_SEC]
    for sid in stale:
        _queues.pop(sid, None)
        _history.pop(sid, None)
        _last_seen.pop(sid, None)
        _rate_buckets.pop(sid, None)


def _rate_limited(session_id: str) -> bool:
    now = time.time()
    bucket = _rate_buckets[session_id]
    # выкидываем устаревшие штампы
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_MIN:
        return True
    bucket.append(now)
    return False


# ── Schemas ────────────────────────────────────────────────────────────────
class MessageIn(BaseModel):
    session_id: str = Field(..., min_length=4, max_length=64)
    text: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LEN)
    page_referrer: str | None = Field(default=None, max_length=500)


# ── Quick-action handlers ───────────────────────────────────────────────────
_QUICK_REPLIES: dict[str, dict[str, Any]] = {
    "/start": {
        "text": (
            "Привет 👋 Я ассистент EDL OS. Расскажу, как мы помогаем "
            "основателям 10–50 человек.\n\n"
            "Что интересно?"
        ),
        "buttons": [
            {"label": "Что такое EDL OS?", "callback": "Что такое EDL OS?"},
            {"label": "Сколько стоит?", "callback": "Сколько стоит?"},
            {"label": "Пройти Founder OS Score", "callback": "Пройти Founder OS Score"},
            {"label": "Связаться с менеджером", "callback": "Связаться с менеджером"},
        ],
    },
    "Пройти Founder OS Score": {
        "text": (
            "Founder OS Score — 12 вопросов по 4 слоям, бесплатно, "
            "результат за 2 минуты.\n\n"
            "Удобнее в Telegram-боте: [@edl_os_bot](https://t.me/edl_os_bot?start=score)\n"
            "Или прямо на сайте — кнопка «Mini-Чекап» в шапке."
        ),
        "buttons": [
            {"label": "Открыть бота", "callback": "/open_bot"},
        ],
    },
    "/open_bot": {
        "text": "Откройте https://t.me/edl_os_bot?start=score — там команда /score уже подставлена.",
        "buttons": [],
    },
    "Связаться с менеджером": {
        "text": (
            "Передам вашу заявку Ивану — он напишет в течение рабочего "
            "дня (10:00–19:00 МСК).\n\n"
            "Или сразу в Telegram: [@lvanKhudyakov](https://t.me/lvanKhudyakov)"
        ),
        "buttons": [],
    },
}


async def _log_event(event: str, payload: dict[str, Any]) -> None:
    try:
        factory = async_session_factory()
        async with factory() as session:
            await session.execute(insert(Event).values(event=event, payload=payload))
            await session.commit()
    except Exception:  # noqa: BLE001 — лог не должен ронять ответ
        logger.exception("widget: failed to log event=%s", event)


async def _notify_admin_handoff(session_id: str, page_referrer: str | None) -> None:
    """Шлём админу алерт в Telegram о запросе менеджера."""
    from src.main import _ptb_app  # циклический импорт — берём бота в рантайме

    if _ptb_app is None or not settings.admin_chat_id:
        return
    msg = (
        "🆘 *Запрос менеджера с сайта*\n"
        f"session: `{session_id}`\n"
        f"page: {page_referrer or 'unknown'}\n"
        f"когда: {time.strftime('%Y-%m-%d %H:%M', time.localtime())}"
    )
    try:
        await _ptb_app.bot.send_message(
            chat_id=settings.admin_chat_id,
            text=msg,
            parse_mode="Markdown",
        )
    except Exception:  # noqa: BLE001
        logger.exception("widget: failed to notify admin about handoff")


async def _push(session_id: str, payload: dict[str, Any]) -> None:
    q = _get_queue(session_id)
    try:
        q.put_nowait(payload)
    except asyncio.QueueFull:
        logger.warning("widget: queue full for session=%s, dropping payload", session_id)


async def _handle_user_message(session_id: str, text: str, page_referrer: str | None) -> None:
    """Фоновая задача: квик-ответ или LLM → push в SSE."""
    _last_seen[session_id] = time.time()
    history = _history[session_id]

    # 1) Quick-replies — без LLM
    quick = _QUICK_REPLIES.get(text.strip())
    if quick:
        await _push(session_id, quick)
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": quick["text"]})
        del history[:-MAX_HISTORY]
        if text.strip() == "Связаться с менеджером":
            await _notify_admin_handoff(session_id, page_referrer)
            await _log_event("widget_handoff", {"session_id": session_id, "referrer": page_referrer})
        return

    # 2) LLM-ответ
    try:
        response, tokens = await llm_reply(
            user_text=text,
            segment="other",
            stage="cold",
            history=list(history[-MAX_HISTORY:]),
        )
    except Exception:  # noqa: BLE001
        logger.exception("widget: LLM failed for session=%s", session_id)
        await _push(
            session_id,
            {
                "text": (
                    "Что-то пошло не так на нашей стороне. Попробуйте через "
                    "минуту, или напишите в Telegram: @edl_os_bot"
                ),
                "buttons": [],
            },
        )
        return

    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": response})
    del history[:-MAX_HISTORY]

    await _push(session_id, {"text": response, "buttons": []})
    await _log_event(
        "widget_reply",
        {"session_id": session_id, "tokens": tokens, "referrer": page_referrer},
    )


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/message", status_code=202)
async def post_message(body: MessageIn) -> dict[str, str]:
    if not _valid_session(body.session_id):
        raise HTTPException(status_code=400, detail="invalid session_id")
    if _rate_limited(body.session_id):
        raise HTTPException(status_code=429, detail="rate limited")

    _gc_expired_sessions()
    asyncio.create_task(
        _handle_user_message(body.session_id, body.text, body.page_referrer)
    )
    return {"status": "accepted"}


@router.get("/stream/{session_id}")
async def stream(session_id: str, request: Request) -> StreamingResponse:
    if not _valid_session(session_id):
        raise HTTPException(status_code=400, detail="invalid session_id")
    _last_seen[session_id] = time.time()
    queue = _get_queue(session_id)

    async def event_source():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=SSE_HEARTBEAT_SEC)
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"  # SSE-комментарий, держит соединение
        finally:
            logger.info("widget: SSE closed for session=%s", session_id)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # Railway/nginx — не буферим SSE
            "Connection": "keep-alive",
        },
    )
