"""Стикеры: запрещены в manufacturing/wholesale + при stage=hot + при отказе."""
import random

from src.core.stickers import StickerContext, should_send_sticker


def test_manufacturing_never_gets_sticker():
    ctx = StickerContext(segment="manufacturing", stage="cold", trigger="first_response")
    rng = random.Random(0)
    assert should_send_sticker(ctx, rng=rng) is False


def test_wholesale_never_gets_sticker():
    ctx = StickerContext(segment="wholesale", stage="cold", trigger="first_response")
    assert should_send_sticker(ctx) is False


def test_hot_stage_blocks_sticker():
    ctx = StickerContext(segment="b2b_saas", stage="hot", trigger="first_response")
    assert should_send_sticker(ctx) is False


def test_refusal_blocks_sticker():
    ctx = StickerContext(
        segment="marketplace_accounting",
        stage="cold",
        trigger="first_response",
        last_response_was_refusal=True,
    )
    assert should_send_sticker(ctx) is False


def test_allowed_trigger_only():
    ctx = StickerContext(segment="other", stage="cold", trigger="random_message")
    assert should_send_sticker(ctx) is False


def test_allowed_with_random_seed_passes():
    ctx = StickerContext(segment="other", stage="cold", trigger="first_response")
    # seed=1 → random() ≈ 0.134 < 0.6 → True (верно для Python 3.12)
    rng = random.Random(1)
    assert should_send_sticker(ctx, rng=rng) is True


def test_allowed_with_random_seed_fails():
    ctx = StickerContext(segment="other", stage="cold", trigger="first_response")
    # подбираем seed где random > 0.6
    rng = random.Random(2)
    # выполняем несколько раз чтобы убедиться, что есть и False
    results = [should_send_sticker(StickerContext(segment="other", stage="cold", trigger="first_response"), rng=rng) for _ in range(20)]
    assert False in results
