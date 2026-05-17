"""Регрессия: POST /webhook не должен блокировать ответ Telegram'у.

До фикса 17.05.2026 webhook handler вызывал `await process_update(update)`
напрямую, что блокировало HTTP-ответ Telegram'у пока ВСЕ хендлеры не
отработают. Если хендлер делал LLM-вызов (Claude Haiku ~10 сек) или
медленный DB-запрос, Railway proxy таймаутил на ~30 сек и отдавал 502
Bad Gateway. Telegram повторял один и тот же update до 24 часов.

После фикса: webhook кладёт update в `update_queue.put(update)` и сразу
возвращает 200 OK. Обработка — асинхронно через `_update_fetcher` (та
же фоновая таска, что и в polling mode).

Этот тест защищает от регрессии.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _build_mock_app(captured_queue: list):
    """Собирает фиктивный PTB Application с queue, фиксирующей puts."""
    ptb = MagicMock()
    ptb.update_queue = MagicMock()

    async def fake_put(update):
        captured_queue.append(update)

    ptb.update_queue.put = fake_put
    ptb.process_update = AsyncMock(
        side_effect=AssertionError(
            "process_update must NOT be called from webhook handler — "
            "it should go through update_queue to avoid blocking Telegram"
        )
    )
    ptb.bot = MagicMock()
    return ptb


@pytest.fixture
def webhook_app(monkeypatch):
    """FastAPI client с залоченным _ptb_app — без поднятия lifespan."""
    import src.main as main_mod

    captured: list = []
    fake_ptb = _build_mock_app(captured)
    monkeypatch.setattr(main_mod, "_ptb_app", fake_ptb)

    # de_json просто прокидываем dict как «update»
    with patch("src.main.Update.de_json", side_effect=lambda data, bot: data):
        yield main_mod.api, captured


def test_webhook_puts_update_in_queue_not_direct_process(webhook_app):
    api, captured = webhook_app
    client = TestClient(api)

    payload = {"update_id": 1, "message": {"text": "/start"}}
    resp = client.post("/webhook", json=payload)

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert captured == [payload], "Update must land in update_queue"


def test_webhook_returns_quickly_even_if_processing_is_slow(webhook_app, monkeypatch):
    """Главное: даже если фоновая обработка задерживается на 30+ сек,
    webhook endpoint отвечает 200 мгновенно. До фикса — отвечал только
    после процессинга и валился по Railway proxy timeout.
    """
    import time

    api, captured = webhook_app
    client = TestClient(api)

    start = time.monotonic()
    resp = client.post("/webhook", json={"update_id": 2})
    elapsed = time.monotonic() - start

    assert resp.status_code == 200
    assert elapsed < 0.5, (
        f"webhook took {elapsed:.2f}s — must return <0.5s regardless of handler work"
    )


def test_webhook_rejects_wrong_secret_token(webhook_app, monkeypatch):
    """Если задан WEBHOOK_SECRET_TOKEN, запросы без правильного заголовка
    отвергаются с 401 (защита от поддельных webhook).
    """
    import src.main as main_mod

    monkeypatch.setattr(main_mod.settings, "webhook_secret_token", "my-secret-token")

    api, _ = webhook_app
    client = TestClient(api)

    resp = client.post("/webhook", json={"update_id": 3})
    assert resp.status_code == 401

    resp = client.post(
        "/webhook",
        json={"update_id": 3},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-token"},
    )
    assert resp.status_code == 401

    resp = client.post(
        "/webhook",
        json={"update_id": 3},
        headers={"X-Telegram-Bot-Api-Secret-Token": "my-secret-token"},
    )
    assert resp.status_code == 200


def test_webhook_returns_503_if_app_not_ready(monkeypatch):
    """Если _ptb_app ещё не инициализирован (lifespan не отработал) —
    отдаём 503, не падаем."""
    import src.main as main_mod

    monkeypatch.setattr(main_mod, "_ptb_app", None)

    client = TestClient(main_mod.api)
    resp = client.post("/webhook", json={"update_id": 4})
    assert resp.status_code == 503


def test_health_endpoint_works():
    """Smoke: /health отдаёт 200 + JSON с ключами."""
    import src.main as main_mod

    client = TestClient(main_mod.api)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "use_webhook" in body
    assert "payment_mode" in body
