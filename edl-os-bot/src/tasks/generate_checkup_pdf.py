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


async def _generate(application_id: str) -> str:
    """Основная логика генерации PDF."""
    from uuid import UUID
    from sqlalchemy import select
    from src.core.checkup_report import render_report
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

    html = render_report(application=app, user=user, answers=list(answers))

    import tempfile, os
    from pathlib import Path

    try:
        from weasyprint import HTML
        out_dir = Path("/var/data/checkups")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"checkup_{application_id}.pdf"
        HTML(string=html).write_pdf(str(out_path))
        pdf_url = f"/var/data/checkups/checkup_{application_id}.pdf"
    except ImportError:
        logger.warning("WeasyPrint not available, saving HTML only")
        out_path = Path(tempfile.mktemp(suffix=".html"))
        out_path.write_text(html, encoding="utf-8")
        pdf_url = str(out_path)

    # Сохраняем URL в Application
    async with factory() as session:
        app = await session.get(Application, app_uuid)
        if app:
            app.checkup_pdf_url = pdf_url
        await session.commit()

    # Отправляем PDF пользователю через PTB (best effort)
    try:
        from src.main import _ptb_app
        from src.db.models import User as UserModel
        async with factory() as session:
            u = await session.get(UserModel, app.user_id if app else None)
        if _ptb_app and u:
            if pdf_url.endswith(".pdf") and os.path.exists(pdf_url):
                with open(pdf_url, "rb") as f:
                    await _ptb_app.bot.send_document(
                        chat_id=u.telegram_id,
                        document=f,
                        filename=f"EDL_OS_Checkup_{application_id[:8]}.pdf",
                        caption=(
                            "PDF-черновик Чекапа готов. "
                            "Катя проверит и пришлёт финальную версию."
                        ),
                    )
    except Exception:
        logger.exception("Failed to send PDF to user for application %s", application_id)

    logger.info("generate_checkup_pdf done for %s: %s", application_id, pdf_url)
    return pdf_url
