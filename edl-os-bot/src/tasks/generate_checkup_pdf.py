"""Celery-таск: генерация PDF-черновика Чекапа по итогам 20 ответов."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from src.tasks.celery_app import celery_app

    @celery_app.task(name="generate_checkup_pdf")
    def generate_checkup_pdf(application_id: str) -> str:
        """Синхронная точка входа Celery → делегирует в asyncio."""
        import asyncio
        return asyncio.run(_generate(application_id))

except Exception:
    # Celery не настроен (локальная разработка без Redis) — graceful fallback
    class _FakeSig:
        def delay(self, *a, **kw):
            logger.warning("Celery not configured, generate_checkup_pdf skipped for %s", a)

    generate_checkup_pdf = _FakeSig()  # type: ignore[assignment]


_PDF_STORAGE_DIR = "/var/data/checkups"


def _pdf_storage_root() -> "Path":
    """Корень хранения PDF.

    Railway: /var/data/checkups (volume).
    Локально: /tmp/edl_checkups (создаётся при первом запуске).
    Будущая миграция в Selectel S3 — менять только эту функцию.
    """
    from pathlib import Path
    import os

    if os.path.isdir("/var/data"):
        return Path(_PDF_STORAGE_DIR)
    return Path("/tmp/edl_checkups")


def resolve_pdf_path(stored_url: str | None) -> "Path | None":
    """Возвращает абсолютный путь к PDF из значения checkup_pdf_url.

    Принимает и относительные («checkup_<uuid>.pdf»), и легаси-абсолютные
    («/var/data/checkups/checkup_<uuid>.pdf») значения.
    """
    from pathlib import Path

    if not stored_url:
        return None
    p = Path(stored_url)
    if p.is_absolute():
        return p if p.exists() else None
    candidate = _pdf_storage_root() / stored_url
    return candidate if candidate.exists() else None


async def _generate(application_id: str) -> str:
    """Основная логика генерации PDF.

    Маршрутизация (требование ТЗ Чекап Plus v2.0 §5):
    - Если env-флаг CHECKUP_PDF_V3_ENABLED == "1" (по умолчанию выключен),
      рендерим новый шаблон Екатерины через Claude Haiku 4.5 →
      `core.checkup_pdf_v3`. Это даёт A4-вёрстку 12/16 страниц с SVG-схемами,
      score-ring, deep-dive Plus, тремя путями решения, юр-футером.
    - Иначе — старый v2 рендер (`core.checkup_report_v2`) для обратной
      совместимости с уже запущенными в проде Чекапами.
    """
    import os
    from uuid import UUID
    from sqlalchemy import select
    from src.db.models import Application, CheckupAnswer, User
    from src.db.session import async_session_factory

    app_uuid = UUID(application_id)
    factory = async_session_factory()
    async with factory() as session:
        app = await session.get(Application, app_uuid)
        if app is None:
            logger.error("generate_checkup_pdf: application %s not found", application_id)
            return ""
        user = await session.get(User, app.user_id)
        answers = (
            await session.execute(
                select(CheckupAnswer).where(CheckupAnswer.application_id == app_uuid)
            )
        ).scalars().all()

    use_v3 = os.getenv("CHECKUP_PDF_V3_ENABLED", "").strip() in ("1", "true", "yes", "on")
    if use_v3:
        try:
            html = await _render_v3(app=app, user=user, answers=list(answers))
        except Exception:
            logger.exception(
                "checkup_pdf_v3 failed for %s, falling back to v2", application_id
            )
            from src.core.checkup_report_v2 import render_report_v2
            html = render_report_v2(application=app, user=user, answers=list(answers))
    else:
        from src.core.checkup_report_v2 import render_report_v2
        html = render_report_v2(application=app, user=user, answers=list(answers))

    import tempfile
    from pathlib import Path

    relative_name = f"checkup_{application_id}.pdf"
    storage_root = _pdf_storage_root()
    storage_root.mkdir(parents=True, exist_ok=True)
    out_path = storage_root / relative_name

    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(str(out_path))
        # В БД храним относительный путь — backend-агностично (Volume/S3).
        stored_value = relative_name
    except ImportError:
        logger.warning("WeasyPrint not available, saving HTML only")
        out_path = Path(tempfile.mktemp(suffix=".html"))
        out_path.write_text(html, encoding="utf-8")
        stored_value = str(out_path)  # absolute fallback, локалка

    # Сохраняем относительный путь в Application
    async with factory() as session:
        app = await session.get(Application, app_uuid)
        if app:
            app.checkup_pdf_url = stored_value
        await session.commit()

    # Отправляем PDF клиенту через PTB (best effort)
    try:
        from src.main import _ptb_app
        from src.db.models import User as UserModel
        async with factory() as session:
            u = await session.get(UserModel, app.user_id if app else None)
        if _ptb_app and u and out_path.exists() and out_path.suffix == ".pdf":
            plan = (app.payload or {}).get("plan", "base") if app and app.payload else "base"
            plus_video_line = (
                "\n\nВидео-разбор от Кати придёт в течение 24 часов."
                if plan == "plus" and not (app.payload or {}).get("is_self_demo")
                else ""
            )
            with open(out_path, "rb") as f:
                await _ptb_app.bot.send_document(
                    chat_id=u.telegram_id,
                    document=f,
                    filename=f"EDL_OS_Checkup_{application_id[:8]}.pdf",
                    caption=(
                        "📄 Ваш Бизнес-чекап готов.\n"
                        "Внутри — диагноз по 4 слоям, конкретные рекомендации "
                        "и 3 сценария под ваши приоритетные метрики."
                        f"{plus_video_line}"
                    ),
                )
    except Exception:
        logger.exception("Failed to send PDF to user for application %s", application_id)

    logger.info("generate_checkup_pdf done for %s: %s", application_id, stored_value)
    return stored_value


async def _render_v3(*, app, user, answers) -> str:
    """Адаптер v2 → v3: маппит CheckupAnswer и метаданные в data dict
    для нового шаблона Екатерины, рендерит HTML через checkup_pdf_v3.

    Маппинг ответов:
    - Q1.1..Q4.4 (SPIN) — берём из CheckupAnswer.text если question_key
      совпадает (для будущей версии FSM). Иначе используем legacy 20-quiz
      ответы как «контекстный текст» для Claude (фактически — fallback).
    """
    from src.core.checkup_pdf_v3 import build_pdf_data, render_pdf_html
    from src.core.checkup_spin_questions import SPIN_QUESTIONS

    # Соберём ответы: пытаемся подобрать v2-spin ключи Q1.1..Q4.4, иначе
    # берём первые 16 ответов клиента в порядке слоёв.
    spin_keys = [q.id for q in SPIN_QUESTIONS]
    answer_map: dict[str, str] = {}
    for a in answers:
        if a.question_key in spin_keys:
            answer_map[a.question_key] = a.text or ""
    if not answer_map:
        # Legacy 20-quiz — берём как контекст. Claude всё равно работает
        # по архетипу и общим бенчмаркам.
        layer_buckets = {"strategy": [], "funnel": [], "operations": [], "money": []}
        legacy_to_layer = {
            "sales": "funnel", "operations": "operations", "finance": "money",
            "strategy": "strategy",
        }
        for a in answers:
            layer = legacy_to_layer.get(a.layer or "", "strategy")
            if a.text:
                layer_buckets[layer].append(a.text)
        # Заполняем Q*.1 первым ответом слоя и т.д. — приблизительно.
        layer_to_qids = {
            "strategy": ["Q1.1", "Q1.2", "Q1.3", "Q1.4"],
            "funnel": ["Q2.1", "Q2.2", "Q2.3", "Q2.4"],
            "operations": ["Q3.1", "Q3.2", "Q3.3", "Q3.4"],
            "money": ["Q4.1", "Q4.2", "Q4.3", "Q4.4"],
        }
        for layer, qids in layer_to_qids.items():
            bucket = layer_buckets[layer]
            for i, qid in enumerate(qids):
                if i < len(bucket):
                    answer_map[qid] = bucket[i]

    plan = "plus" if (app.payload or {}).get("plan") == "plus" else "basic"
    company_legal_name = (
        (app.payload or {}).get("company_legal_name")
        or (user.company_name if user else None)
        or "ваша компания"
    )
    report_id = (
        (app.payload or {}).get("report_id")
        or f"EDL-CHK-{app.inv_id:06d}" if hasattr(app, "inv_id") else f"EDL-CHK-{str(app.id)[:8]}"
    )

    data = await build_pdf_data(
        plan=plan,
        company_legal_name=company_legal_name,
        segment=user.segment if user else None,
        stage=user.stage if user else None,
        spin_answers=answer_map,
        report_id=report_id,
        answers_count=len(answer_map) or 16,
    )
    return render_pdf_html(data)
