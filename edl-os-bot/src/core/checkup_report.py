"""Генерация HTML-отчёта Чекапа для WeasyPrint."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.core.checkup_questions import by_key, determine_vat_zone
from src.core.config import settings
from src.db.models import Application, CheckupAnswer, User

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )


def _group_answers(answers: list[CheckupAnswer]) -> dict[str, list[dict]]:
    questions = by_key()
    layers: dict[str, list[dict]] = {
        "strategy": [], "sales": [], "operations": [], "finance": []
    }
    for a in sorted(answers, key=lambda x: questions.get(x.question_key, type("_", (), {"order": 99})).order if x.question_key in questions else 99):  # type: ignore
        q = questions.get(a.question_key)
        if q is None:
            continue
        notes = []
        if a.quality_notes:
            try:
                notes = json.loads(a.quality_notes)
            except Exception:
                notes = [a.quality_notes]
        layers.setdefault(a.layer, []).append({
            "order": q.order,
            "question": q.text,
            "answer": a.text,
            "quality_passed": a.quality_passed,
            "quality_notes": notes,
            "skipped": a.text == "[пропущено]",
        })
    return layers


def _quality_summary(answers: list[CheckupAnswer]) -> dict:
    total = len(answers)
    passed = sum(1 for a in answers if a.quality_passed)
    return {"total": total, "passed": passed, "failed": total - passed}


def render_vat_section(answers: list[CheckupAnswer]) -> str:
    """F2: Генерирует HTML-раздел «НДС-флажок 2026» для отчёта.

    Использует ответы на m2_ebitda (выручка) и m3_tax (налоговый режим).
    Возвращает пустую строку если нужные ответы не найдены.
    """
    revenue_answer = next(
        (a for a in answers if a.question_key in ("m2_ebitda", "m3_tax")),
        None,
    )
    if not revenue_answer:
        return ""

    vat_info = determine_vat_zone(revenue_answer.text)
    zone = vat_info["zone"]
    zone_color = {
        "below_threshold": "#22c55e",
        "approaching": "#f59e0b",
        "first_time": "#ef4444",
        "established": "#6b7280",
    }.get(zone, "#6b7280")

    return (
        f'<div class="vat-section" style="border-left:4px solid {zone_color};'
        f'padding:12px 16px;margin:24px 0;background:#fafafa;">'
        f"<h2>НДС-флажок 2026</h2>"
        f'<p><strong>Ваша зона:</strong> {vat_info["description"]}</p>'
        f'<p><strong>Что делать:</strong> {vat_info["advice"]}</p>'
        f"</div>"
    )


def render_report(
    *,
    application: Application,
    user: User,
    answers: list[CheckupAnswer],
    quiz_layers: dict[str, int] | None = None,
    quiz_score: int | None = None,
) -> str:
    """Возвращает HTML-строку отчёта, готовую к WeasyPrint."""
    plan = (application.payload or {}).get("plan", "base") if application.payload else "base"
    full_name = " ".join(filter(None, [user.last_name, user.first_name])) or "—"
    ctx = {
        "company": user.company_name or "—",
        "full_name": full_name,
        "plan": plan,
        "plan_label": "Plus" if plan == "plus" else "Базовый",
        "generated_at": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
        "quiz_score": quiz_score,
        "quiz_layers": quiz_layers,
        "answers_by_layer": _group_answers(answers),
        "quality_summary": _quality_summary(answers),
        "offer_url": settings.offer_checkup_url,
        "vat_section_html": render_vat_section(answers),
        "is_draft": True,
    }
    try:
        template = _env().get_template("checkup_report.html")
        return template.render(**ctx)
    except Exception:
        # Fallback: minimal HTML если шаблон не найден
        return _minimal_html(ctx)


def _minimal_html(ctx: dict) -> str:
    layers_html = ""
    for layer, items in ctx["answers_by_layer"].items():
        if not items:
            continue
        layer_label = {"strategy": "Стратегия", "sales": "Воронка", "operations": "Операционка", "finance": "Деньги"}.get(layer, layer)
        layers_html += f"<h2>{layer_label}</h2>"
        for item in items:
            quality = "✅" if item["quality_passed"] else ("⏭" if item["skipped"] else "⚠️")
            layers_html += (
                f"<h3>{quality} {item['order']}. {item['question']}</h3>"
                f"<p>{item['answer']}</p>"
            )
    qs = ctx["quality_summary"]
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>Бизнес-чекап EDL OS — {ctx['company']}</title>
<style>body{{font-family:Inter,sans-serif;max-width:800px;margin:40px auto;padding:0 20px;color:#1a1a1a}}
h1{{color:#2D6A4F}}h2{{color:#40916C;border-bottom:2px solid #B7E4C7;padding-bottom:8px}}
h3{{color:#1B4332}}p{{background:#F8F9FA;padding:12px;border-radius:8px;border-left:4px solid #74C69D}}
.watermark{{background:#FFF3CD;border:1px solid #FFD43B;padding:16px;border-radius:8px;margin:20px 0}}
.meta{{color:#666;font-size:14px}}</style>
</head>
<body>
<div class="watermark">⚠️ ЧЕРНОВИК — ожидает ревью команды EDL OS</div>
<h1>Бизнес-чекап EDL OS</h1>
<div class="meta">
  <p>Компания: {ctx['company']} | ФИО: {ctx['full_name']} | Тариф: {ctx['plan_label']}</p>
  <p>Дата: {ctx['generated_at']} | Качество: {qs['passed']}/{qs['total']} ответов прошли рубрику</p>
</div>
{layers_html}
<hr>
<p class="meta">Оферта: <a href="{ctx['offer_url']}">{ctx['offer_url']}</a><br>
Финальный разбор будет добавлен после ручной проверки командой EDL OS.</p>
</body></html>"""
