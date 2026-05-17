"""Регрессия: lifespan НЕ должен вызывать delete_webhook при выключении.

Контекст 17.05.2026: после мерджа PR с миграциями (preDeployCommand) Railway
передеплоил, новый контейнер запустился и сделал set_webhook → URL OK. Но
старый контейнер при SIGTERM выполнил finally → delete_webhook() → URL в
Telegram стёрт. Telegram перестал слать апдейты (pending_update_count рос,
url=""). Бот молчал на /start и /admin_login.

Корневая причина — race: rolling deploy не гарантирует, что delete_webhook
старого контейнера произойдёт ДО set_webhook нового. set_webhook идемпотентен,
delete_webhook — деструктивен.

Этот тест защищает от регрессии: если кто-то снова добавит delete_webhook в
lifespan finally — тест упадёт.
"""
from __future__ import annotations

from pathlib import Path

MAIN_PY = Path(__file__).resolve().parent.parent / "src" / "main.py"


def _strip_comments_and_strings(src: str) -> str:
    """Remove # comments and triple-quoted blocks so we only inspect real code."""
    import re

    # remove triple-quoted strings (docstrings + multi-line comments)
    no_triple = re.sub(r'"""[\s\S]*?"""', "", src)
    no_triple = re.sub(r"'''[\s\S]*?'''", "", no_triple)
    # remove single-line # comments
    lines = []
    for line in no_triple.splitlines():
        if "#" in line:
            line = line.split("#", 1)[0]
        lines.append(line)
    return "\n".join(lines)


def test_lifespan_does_not_call_delete_webhook():
    text = MAIN_PY.read_text(encoding="utf-8")
    # set_webhook остаётся (новый контейнер должен его установить при старте)
    assert "set_webhook" in text, "set_webhook must remain — new container sets it at startup"
    # Проверяем только КОД (без комментариев и docstring'ов).
    code_only = _strip_comments_and_strings(text)
    assert "delete_webhook" not in code_only, (
        "delete_webhook() must NOT be called from lifespan — on Railway rolling "
        "deploys the old container's finally block can race the new container's "
        "set_webhook and leave the webhook URL empty, breaking the bot. "
        "Explanatory comments mentioning the function are fine; calls are not."
    )
