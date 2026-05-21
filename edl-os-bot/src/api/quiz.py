"""Mini-Чекап v2 — публичное API для сайта и внутренний эндпоинт для бота.

POST /api/quiz/submit  — принимает ответы с сайта, считает Score, сохраняет.
GET  /internal/quiz/{id} — возвращает submission по UUID (для бота при deep-link).
"""
from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, field_validator

from src.core.benchmarks import benchmark_for
from src.core.config import settings
from src.core.growth_hints import hint_for
from src.core.quiz import (
    LAYER_LABEL,
    QUIZ_QUESTIONS,
    SEGMENT_LABEL,
    STAGE_FROM_P2,
    STAGE_LABEL,
    VALID_SCORES,
    build_result,
    stage_detection,
)
from src.db.repos import get_quiz_submission, mark_quiz_completed
from src.db.session import async_session_factory

router = APIRouter()

_ALLOWED_SEGMENTS = set(SEGMENT_LABEL.keys())
_ALLOWED_P2_OPTS = set(STAGE_FROM_P2.keys())
_ALL_QUESTION_KEYS = {q.key for q in QUIZ_QUESTIONS}

# Rate limit: 5 req / hour per IP (Redis sliding window)
_RATE_LIMIT_WINDOW = 3600
_RATE_LIMIT_MAX = 5


async def _check_rate_limit(ip: str) -> None:
    """Raises 429 если IP превысил лимит."""
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        key = f"quiz_submit_rl:{ip}"
        async with r:
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, _RATE_LIMIT_WINDOW)
            if count > _RATE_LIMIT_MAX:
                raise HTTPException(
                    status_code=429,
                    detail="Слишком много попыток. Повторите через час.",
                )
    except HTTPException:
        raise
    except Exception:
        # Redis недоступен — пропускаем (не блокируем пользователя)
        pass


class QuizSubmitRequest(BaseModel):
    source: Literal["site_page", "site_widget"]
    widget_session_id: uuid.UUID | None = None
    segment: str
    stage_from_p2: str
    answers: dict[str, int]
    duration_sec: int | None = None
    email: str | None = None
    consent_marketing: bool = False

    @field_validator("segment")
    @classmethod
    def validate_segment(cls, v: str) -> str:
        if v not in _ALLOWED_SEGMENTS:
            raise ValueError(f"segment must be one of {sorted(_ALLOWED_SEGMENTS)}")
        return v

    @field_validator("stage_from_p2")
    @classmethod
    def validate_stage(cls, v: str) -> str:
        if v not in _ALLOWED_P2_OPTS:
            raise ValueError(f"stage_from_p2 must be one of {sorted(_ALLOWED_P2_OPTS)}")
        return v

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, v: dict[str, int]) -> dict[str, int]:
        missing = _ALL_QUESTION_KEYS - set(v.keys())
        if missing:
            raise ValueError(f"Missing answers for: {sorted(missing)}")
        invalid = {k: sc for k, sc in v.items() if sc not in VALID_SCORES}
        if invalid:
            raise ValueError(f"Invalid scores (must be 0/3/5/8/10): {invalid}")
        return v


def _build_response(submission_id: uuid.UUID, req: QuizSubmitRequest) -> dict[str, Any]:
    """Строим ответ для клиента без зависимости от БД-объекта."""
    stage, conf = stage_detection(req.stage_from_p2)
    result = build_result(req.answers, stage, req.segment, stage_confidence=conf)

    bm_mean = result.benchmark_mean
    bm_delta = result.benchmark_delta
    bm_source = "hardcoded" if bm_mean is not None else None

    deep_link = (
        f"https://t.me/{settings.bot_username}?start=audit_from_score_{submission_id}"
    )

    cta_labels = {
        "audit":               "Бизнес-чекап · 9 000 ₽",
        "audit_plus":          "Чекап Plus · 14 000 ₽",
        "diagnostic_waitlist": "Диагностика — лист ожидания",
    }
    sec_labels = {
        "audit":      "Бизнес-чекап · 9 000 ₽",
        "audit_plus": "Чекап Plus · 14 000 ₽",
        "demo":       "Сначала поговорить",
    }

    return {
        "quiz_session_id": str(submission_id),
        "score": result.score,
        "category": result.category,
        "category_color": result.category_color,
        "stage": result.stage,
        "stage_label": result.stage_label,
        "stage_confidence": result.stage_confidence,
        "segment": result.segment,
        "segment_label": result.segment_label,
        "layer_scores": dict(result.layer_scores),
        "benchmark": {
            "mean": bm_mean,
            "delta": bm_delta,
            "source": bm_source,
        },
        "growth_points": [
            {
                "layer": gp.layer,
                "layer_label": gp.layer_label,
                "short": gp.short,
                "action": gp.action,
            }
            for gp in result.growth_points
        ],
        "cta": {
            "primary": {
                "type": result.cta_primary,
                "label": cta_labels.get(result.cta_primary, ""),
                "deep_link": deep_link,
            },
            "secondary": {
                "type": result.cta_secondary,
                "label": sec_labels.get(result.cta_secondary, ""),
            },
        },
    }


@router.post("/api/quiz/submit")
async def quiz_submit(req: QuizSubmitRequest, request: Request) -> dict[str, Any]:
    """Принимает ответы с сайта, считает Score, сохраняет в БД."""
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    client_ip = client_ip.split(",")[0].strip()
    await _check_rate_limit(client_ip)

    stage, conf = stage_detection(req.stage_from_p2)
    result = build_result(req.answers, stage, req.segment, stage_confidence=conf)

    outlier_flag = None
    if req.stage_from_p2 == "outlier_small_team":
        outlier_flag = "small_team"
    elif req.stage_from_p2 == "outlier_big_team":
        outlier_flag = "big_team"

    async with async_session_factory()() as session:
        # Создаём submission без user_id (публичный эндпоинт, нет авторизации)
        from src.db.models import QuizSubmission
        submission = QuizSubmission(
            user_id=None,
            source=req.source,
            widget_session_id=req.widget_session_id,
            segment=req.segment,
            stage=stage,
            stage_confidence=conf,
            outlier_flag=outlier_flag,
            score=result.score,
            layer_scores=dict(result.layer_scores),
            answers=req.answers,
            growth_points=[
                {"layer": gp.layer, "layer_label": gp.layer_label,
                 "question_key": gp.question_key, "short": gp.short, "action": gp.action}
                for gp in result.growth_points
            ],
            duration_sec=req.duration_sec,
            consent_marketing_at_submit=req.consent_marketing,
            email=req.email if req.consent_marketing else None,
        )
        session.add(submission)
        await session.flush()
        submission_id = submission.id
        await session.commit()

    return _build_response(submission_id, req)


@router.get("/internal/quiz/{quiz_session_id}")
async def get_quiz_by_session(
    quiz_session_id: uuid.UUID,
    x_internal_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Внутренний эндпоинт — используется ботом при deep-link audit_from_score_<UUID>."""
    if not settings.internal_api_token:
        raise HTTPException(status_code=503, detail="Internal API not configured")
    if x_internal_token != settings.internal_api_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    async with async_session_factory()() as session:
        sub = await get_quiz_submission(session, quiz_session_id)
        if not sub:
            raise HTTPException(status_code=404, detail="Quiz session not found")

    return {
        "quiz_session_id": str(sub.id),
        "segment":      sub.segment,
        "stage":        sub.stage,
        "stage_confidence": sub.stage_confidence,
        "score":        sub.score,
        "layer_scores": sub.layer_scores,
        "answers":      sub.answers,
        "growth_points": sub.growth_points,
        "source":       sub.source,
    }
