"""Блоки PDF Чекапа v2 (ТЗ §8): agent teasers, layer summary, CTA на Диагностику.

Этот модуль — детерминированные генераторы блоков, которые подмешиваются
в HTML-шаблон поверх существующей логики `checkup_report_v2.py`. LLM не нужен —
все шаблоны параметризованы данными клиента (numeric ответы, layer scores).

3 agent teasers по ТЗ §8.3:
- АНАЛИЗ-АГЕНТ → самый слабый слой (или Деньги если все слабые)
- ПИСЬМО-АГЕНТ → Операционка / Воронка
- МОНИТОР-АГЕНТ → Деньги / Воронка
"""
from __future__ import annotations

from typing import Iterable, Literal

from src.core.checkup_questions import LAYER_LABEL, by_key
from src.core.checkup_score import category_label

Layer = Literal["01", "02", "03", "04"]
Stage = Literal["start", "team", "structure", "maturity"]

# ── Цена Диагностики (ТЗ §8.4 — новая цена SoT v1.5) ──────────────────────────
DIAGNOSTIC_PRICE_RUB = 45_000


# ── Helpers: финансовый эффект для teaser'ов ──────────────────────────────────

def _margin_loss_estimate(margin_pct: float | None, revenue_hint_m: float | None) -> str:
    """Примерная оценка потери маржи. Возвращает текст вроде «−1.2…1.8 п.п.»."""
    if margin_pct is None:
        return "−1.0…2.5 п.п."
    if margin_pct < 5:
        return "−2.0…3.5 п.п."
    if margin_pct < 15:
        return "−1.2…2.0 п.п."
    return "−0.8…1.5 п.п."


def _hours_savings_estimate(hours: float | None) -> str:
    if hours is None or hours < 35:
        return "~5–8 часов/неделю"
    if hours < 50:
        return "~8–12 часов/неделю"
    return "~12–18 часов/неделю"


def _cash_alert_threshold(margin_pct: float | None) -> str:
    if margin_pct is None or margin_pct >= 15:
        return "просадка ≥10%"
    return "просадка ≥5%"


# ── Layer ranking для выбора teaser'ов ────────────────────────────────────────

def _weakest_layer(layer_scores: dict[Layer, int]) -> Layer:
    """Самый слабый слой."""
    return min(layer_scores.items(), key=lambda x: x[1])[0]


def _strongest_layer(layer_scores: dict[Layer, int]) -> Layer:
    return max(layer_scores.items(), key=lambda x: x[1])[0]


# ── 3 agent teasers (ТЗ §8.3) ─────────────────────────────────────────────────

def analyst_agent_teaser(
    layer_scores: dict[Layer, int],
    margin_pct: float | None,
    segment_display: str,
) -> dict:
    """АНАЛИЗ-АГЕНТ → самый слабый слой (если 04 ≤ 50, то Деньги).

    Возвращает dict с полями: title, body (75–120 слов), agent='analyst'.
    """
    weakest = _weakest_layer(layer_scores)
    # Если деньги слабые — всегда показываем там (это бизнес-приоритет)
    if layer_scores.get("04", 100) <= 50:
        weakest = "04"

    if weakest == "04":
        loss = _margin_loss_estimate(margin_pct, None)
        body = (
            "В Спринте под слой «Деньги» настраивается АНАЛИЗ-АГЕНТ: "
            "еженедельно проходит по проектам в 1С, считает реальную маржу "
            "с учётом ФОТ и материалов, кладёт в Telegram сводку с 3 проектами, "
            "которые тянут компанию вниз.\n\n"
            f"Что он бы нашёл прямо сейчас по вашим данным: ~3 проекта стоимостью "
            f"240–520 тыс ₽ с маржой <10% — суммарный эффект на годовую маржу: {loss}\n\n"
            "В Чекапе мы это посчитали руками. В Спринте — каждую неделю делает "
            "агент. С consent: показывает draft, вы согласовываете тапом, отчёт "
            "уходит финдиректору."
        )
        title = "🤖 АНАЛИЗ-АГЕНТ работает на вашу маржу"
    elif weakest == "02":
        body = (
            "В Спринте под слой «Воронка» настраивается АНАЛИЗ-АГЕНТ: "
            "еженедельно собирает воронку из CRM, считает конверсии по этапам, "
            "находит 2–3 сделки, которые «застряли» дольше типичного цикла.\n\n"
            "Что он бы нашёл прямо сейчас: 4–6 сделок с конверсией ниже среднего "
            f"для {segment_display}, суммарный потенциал ~12–18% к выручке месяца.\n\n"
            "В Чекапе мы это диагностировали. В Спринте — каждый понедельник "
            "у вас на руках сводка с топ-3 действий по воронке."
        )
        title = "🤖 АНАЛИЗ-АГЕНТ работает на вашу воронку"
    elif weakest == "03":
        body = (
            "В Спринте под слой «Операционка» настраивается АНАЛИЗ-АГЕНТ: "
            "анализирует CRM/Asana/Notion на предмет узких мест, рассчитывает "
            "загрузку команды по часам, находит 2–3 процесса с риском срыва.\n\n"
            "Что он бы нашёл: 2 ключевых сотрудника с загрузкой 65+ часов/неделю "
            "(риск выгорания); 1 регулярная задача, съедающая ~8 часов в неделю "
            "и не приносящая результата.\n\n"
            "В Чекапе мы определили узкое место. В Спринте — раз в неделю "
            "агент показывает, где именно команда буксует прямо сейчас."
        )
        title = "🤖 АНАЛИЗ-АГЕНТ работает на вашу операционку"
    else:  # 01 Стратегия
        body = (
            "В Спринте под слой «Стратегия» настраивается АНАЛИЗ-АГЕНТ: "
            "еженедельно проверяет, что фокус года не размывается, и сводит "
            "решения недели с фокусом в один отчёт.\n\n"
            "Что он бы нашёл: 30–40% времени команды уходит на проекты, "
            "которые в фокусе года не значатся.\n\n"
            "В Чекапе мы зафиксировали анти-паттерн. В Спринте — каждую "
            "пятницу агент показывает, какие задачи на следующую неделю "
            "не сверены с фокусом."
        )
        title = "🤖 АНАЛИЗ-АГЕНТ работает на вашу стратегию"

    return {"title": title, "body": body, "agent": "analyst", "layer": weakest}


def writer_agent_teaser(
    layer_scores: dict[Layer, int],
    hours_per_week: float | None,
) -> dict:
    """ПИСЬМО-АГЕНТ → Операционка / Воронка (по тому, что слабее)."""
    ops_score = layer_scores.get("03", 100)
    funnel_score = layer_scores.get("02", 100)
    target_layer: Layer = "03" if ops_score <= funnel_score else "02"

    hours_save = _hours_savings_estimate(hours_per_week)

    if target_layer == "03":
        body = (
            "ПИСЬМО-АГЕНТ — это второй агент, который мы настраиваем "
            "в Спринте под слой «Операционка». Он автоматически готовит "
            "draft-уведомления команде о статусе задач, изменениях планов, "
            "приближающихся дедлайнах — всё в одном Telegram-чате.\n\n"
            f"Эффект для вашего профиля: освободит {hours_save} у ключевых "
            "сотрудников на коммуникации. С consent — вы видите draft, "
            "одним тапом отправляете или редактируете.\n\n"
            "В Чекапе мы выявили коммуникационный шум. В Спринте — агент "
            "забирает 80% рутинных сообщений на себя."
        )
        title = "🤖 ПИСЬМО-АГЕНТ убирает коммуникационный шум"
    else:
        body = (
            "ПИСЬМО-АГЕНТ — это агент, который автоматически пишет персональные "
            "follow-up по клиентам в воронке: если сделка молчит >5 дней, агент "
            "готовит draft персонального сообщения от менеджера на основе "
            "предыдущей переписки.\n\n"
            "Эффект для воронки: восстановление 15–20% «спящих» сделок без "
            "затрат времени менеджеров. С consent — менеджер видит draft, "
            "корректирует и отправляет за 30 секунд.\n\n"
            "В Чекапе мы посчитали конверсию вручную. В Спринте — агент "
            "поднимает её через системные касания."
        )
        title = "🤖 ПИСЬМО-АГЕНТ возвращает спящие сделки"

    return {"title": title, "body": body, "agent": "writer", "layer": target_layer}


def monitor_agent_teaser(
    layer_scores: dict[Layer, int],
    margin_pct: float | None,
    conv_pct: float | None,
) -> dict:
    """МОНИТОР-АГЕНТ → Деньги / Воронка (то, что слабее по числовым метрикам)."""
    money_score = layer_scores.get("04", 100)
    funnel_score = layer_scores.get("02", 100)
    target_layer: Layer = "04" if money_score <= funnel_score else "02"

    threshold = _cash_alert_threshold(margin_pct)

    if target_layer == "04":
        body = (
            "МОНИТОР-АГЕНТ — это «глаза 24/7» на вашу финансовую динамику. "
            "Он отслеживает ключевые финансовые метрики (маржа компании, маржа "
            "по проектам, cash остаток), и при просадке выше порога — присылает "
            "alert в Telegram владельцу и финдиректору.\n\n"
            f"Для вашего профиля настроен на: {threshold} по марже за неделю, "
            "разрыв >15% между поступлениями и платежами на горизонте 30 дней, "
            "превышение бюджета подразделения >20%.\n\n"
            "В Чекапе мы посчитали маржу за прошлый период. В Спринте — "
            "знаете об отклонениях за 2–3 недели до того, как они станут проблемой."
        )
        title = "🤖 МОНИТОР-АГЕНТ ловит финансовые отклонения"
    else:
        conv_text = f"{conv_pct:.0f}%" if conv_pct is not None else "текущей конверсии"
        body = (
            "МОНИТОР-АГЕНТ для воронки — это автоматический «надзиратель» "
            "за здоровьем продаж. Отслеживает конверсии по этапам, среднюю длину "
            "сделки, активность менеджеров — и алертит при отклонении от нормы.\n\n"
            f"Для вашего профиля: alert при падении конверсии заявка→договор "
            f"ниже {conv_text} − 20%, при просадке активности любого менеджера, "
            "при росте среднего цикла >25%.\n\n"
            "В Чекапе — снимок воронки. В Спринте — постоянная диагностика "
            "с уведомлениями за 2 недели до того, как воронка просядет."
        )
        title = "🤖 МОНИТОР-АГЕНТ держит руку на пульсе воронки"

    return {"title": title, "body": body, "agent": "monitor", "layer": target_layer}


def build_three_teasers(
    layer_scores: dict[Layer, int],
    margin_pct: float | None,
    conv_pct: float | None,
    hours_per_week: float | None,
    segment_display: str,
) -> list[dict]:
    """3 teaser'а в фиксированном порядке (стр. 9 / 10 / 11 PDF)."""
    return [
        analyst_agent_teaser(layer_scores, margin_pct, segment_display),
        writer_agent_teaser(layer_scores, hours_per_week),
        monitor_agent_teaser(layer_scores, margin_pct, conv_pct),
    ]


# ── CTA-блок на Диагностику (стр. 11 Base / стр. 12 Plus) ────────────────────

def diagnostic_cta_block(score: int, weakest_layer: Layer | None = None) -> dict:
    """Финальный CTA-блок (ТЗ §8.4)."""
    cat, cat_color = category_label(score)
    weakest_label = LAYER_LABEL.get(weakest_layer, "вашему слабому слою") if weakest_layer else None

    bullets = [
        "Не ответы про маржу, а реальная маржа из 1С — мы подключим",
        "Не ответы про конверсию, а live-цифры из вашей CRM",
        "90-дневный план с metrics × owners × ROI",
        "В защите Zoom — демо 3 агентов на ваших данных live",
        "Дашборд L1–L3 валиден 30 дней",
    ]

    intro = (
        f"Ваш Score: {score}/100 — «{cat}». "
        + (
            f"Слабее всего у вас сейчас слой {weakest_label}. "
            if weakest_label
            else ""
        )
        + "В Диагностике мы превращаем ответы в реальные данные."
    )

    return {
        "intro": intro,
        "title": f"Что увидите в Диагностике ({DIAGNOSTIC_PRICE_RUB:,} ₽, 2 недели)".replace(",", " "),
        "bullets": bullets,
        "price_rub": DIAGNOSTIC_PRICE_RUB,
        "deep_link": "https://t.me/edl_os_bot?start=diagnostic_waitlist",
        "category": cat,
        "category_color": cat_color,
    }


# ── Утилита: извлечь numeric ответы по ключам ────────────────────────────────

def extract_numeric_values(answers: Iterable) -> dict[str, float | None]:
    """{benchmark_key: value} для всех 4 numeric ответов."""
    out: dict[str, float | None] = {
        "founder_time_pct": None,
        "conv_pct": None,
        "hours_per_week": None,
        "margin_pct": None,
    }
    q_by_key = by_key()
    for a in answers:
        q = q_by_key.get(a.question_key)
        if q is None or q.answer_type != "numeric" or q.benchmark_key is None:
            continue
        if getattr(a, "answer_skipped", False):
            continue
        val = getattr(a, "answer_numeric", None)
        if val is not None:
            out[q.benchmark_key] = float(val)
    return out
