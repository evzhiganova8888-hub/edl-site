"""Стикеры/кото-эмодзи segment-aware + рандомизация 60% (§7 ТЗ v3).

MVP (Спринт 1): одиночные animated emoji через sendMessage.
V2 (Спринт 4): настоящие стикеры через sendSticker + file_id.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

CAT_EMOJI_POOL = ["🐱", "🐈", "😺", "😻", "😸", "😽"]

# Сегменты, в которых стикеры запрещены (диссонанс).
BLOCKED_SEGMENTS = {"manufacturing", "wholesale"}

# Триггеры, при которых стикеры разрешены.
ALLOWED_TRIGGERS = {"first_response", "payment_success", "goodbye"}


@dataclass(slots=True)
class StickerContext:
    channel: str = "tg"
    segment: str | None = None
    stage: str | None = None
    trigger: str | None = None
    last_response_was_refusal: bool = False


def should_send_sticker(ctx: StickerContext, *, rng: random.Random | None = None) -> bool:
    if ctx.channel != "tg":
        return False
    if ctx.segment in BLOCKED_SEGMENTS:
        return False
    if ctx.stage == "hot":
        return False
    if ctx.last_response_was_refusal:
        return False
    if ctx.trigger not in ALLOWED_TRIGGERS:
        return False
    rng = rng or random
    return rng.random() < 0.6


def pick_emoji(rng: random.Random | None = None) -> str:
    rng = rng or random
    return rng.choice(CAT_EMOJI_POOL)
