"""FAQ — rules-based (§7.8 ТЗ v3). На Этапе 1 — короткая заглушка."""
from __future__ import annotations

import json
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from src.bot import keyboards

_FAQ_JSON = Path(__file__).resolve().parent.parent.parent / "knowledge_base" / "07_faq.json"


def _load_faq() -> list[dict]:
    if not _FAQ_JSON.exists():
        return []
    try:
        return json.loads(_FAQ_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    faqs = _load_faq()
    if not faqs:
        await update.effective_message.reply_text(
            "FAQ-база ещё наполняется. Пока — задайте вопрос текстом, я отвечу. "
            "Если не знаю — передам Ивану.",
            reply_markup=keyboards.back_to_menu(),
        )
        return

    intro = "Частые вопросы:\n\n"
    lines = []
    for idx, item in enumerate(faqs[:11], start=1):
        lines.append(f"{idx}. {item.get('question', '')}")
    intro += "\n".join(lines)
    intro += "\n\nНапишите номер или сам вопрос — отвечу подробно."
    await update.effective_message.reply_text(intro, reply_markup=keyboards.back_to_menu())
