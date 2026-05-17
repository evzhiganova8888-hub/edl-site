"""20 вопросов Бизнес-чекапа EDL OS × 4 слоя × рубрика качества."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class CheckupQuestion:
    key: str
    layer: str            # strategy|sales|operations|finance
    order: int            # 1..20
    text: str
    min_chars: int
    min_words: int
    expects: tuple[str, ...]
    example_good: str
    why_we_ask: str


CHECKUP_QUESTIONS: tuple[CheckupQuestion, ...] = (
    # ===== STRATEGY (5) =====
    CheckupQuestion(
        key="s1_horizon",
        layer="strategy",
        order=1,
        text="Опишите ваш бизнес через 3 года: продукт, выручка, команда.",
        min_chars=120, min_words=25,
        expects=("горизонт", "выручка с единицей", "размер команды", "продукт/сегмент"),
        example_good=(
            "Через 3 года — SaaS для маркетинговых агентств в РФ и СНГ, ARR 120 млн ₽, "
            "команда 25 человек, продукт — три тарифа, ICP — агентства с выручкой "
            "50–500 млн ₽/год. NPS 50, churn ≤ 6% годовых."
        ),
        why_we_ask=(
            "Без 3-летнего горизонта у недельных ставок нет компаса — мы не сможем "
            "проверить, ведут ли они куда-то конкретно."
        ),
    ),
    CheckupQuestion(
        key="s2_bets",
        layer="strategy",
        order=2,
        text="Три главные ставки этого года — с метриками успеха.",
        min_chars=150, min_words=30,
        expects=("3 ставки", "метрика на каждую", "горизонт каждой"),
        example_good=(
            "1) Запуск Enterprise-тарифа: 15 контрактов от 1М ₽ к декабрю. "
            "2) Поднять conversion демо→договор с 12% до 18% (через ROI-кейсы и SDR). "
            "3) Снять CEO с onboarding'а — снизить долю CEO в delivery с 35% до 10%."
        ),
        why_we_ask="Стратегия в EDL OS = осознанный выбор из CRAFT. Три ставки — это и есть выбор.",
    ),
    CheckupQuestion(
        key="s3_not_doing",
        layer="strategy",
        order=3,
        text="Список «что мы НЕ делаем в этом году» — минимум 5 пунктов с обоснованием.",
        min_chars=180, min_words=35,
        expects=("≥5 пунктов", "обоснование", "горизонт"),
        example_good=(
            "Не идём в B2C-розницу (другая воронка). Не работаем с чеком < 200к "
            "(LTV не окупит CAC). Не открываем филиал (фокус на digital-каналах). "
            "Не запускаем мобильное приложение (rendering уже есть в web). "
            "Не нанимаем sales без SaaS-опыта (длинный ramp-up)."
        ),
        why_we_ask="«Что не делаем» сильнее, чем «что делаем» — это и есть фокус.",
    ),
    CheckupQuestion(
        key="s4_antipatterns",
        layer="strategy",
        order=4,
        text="Два главных анти-паттерна, в которые легко скатиться, и как вы их ловите.",
        min_chars=120, min_words=25,
        expects=("2 анти-паттерна", "механизм отлова"),
        example_good=(
            "1) Кастомная разработка под крупного клиента — съест RnD. Ловим: правило "
            "«custom только при контракте 5М+ и продакт-овнере с нашей стороны». "
            "2) Удержание сотрудников выше market на 30%+ — съест маржу. Ловим: "
            "квартальный compensation review с CFO."
        ),
        why_we_ask="Это страховка стратегии. Без неё фокус размывается тихо и незаметно.",
    ),
    CheckupQuestion(
        key="s5_last_90_days",
        layer="strategy",
        order=5,
        text="Что сдвинулось в стратегии за последние 90 дней — какие 1–2 ставки и почему?",
        min_chars=120, min_words=25,
        expects=("конкретное событие", "ставка/решение", "причина"),
        example_good=(
            "Сдвинули релиз Enterprise с Q1 на Q2: два крупных клиента запросили SSO "
            "и SLA 99.9%. Это удлиняет окно до выручки на 8 недель, но увеличивает "
            "средний чек на 40%. Сценарий согласован с CFO."
        ),
        why_we_ask="Стратегия — это не документ, а серия еженедельных решений. Хотим увидеть динамику.",
    ),

    # ===== SALES / FUNNEL (5) =====
    CheckupQuestion(
        key="f1_funnel_home",
        layer="sales", order=6,
        text="Где живёт ваша воронка и кто её ведёт? Структура + ownership по этапам.",
        min_chars=150, min_words=30,
        expects=("инструмент (CRM/Sheets/иное)", "owner каждого этапа", "регулярность апдейта"),
        example_good=(
            "HubSpot CRM. Лиды собирает CMO Аня (inbound + outbound через SDR). "
            "Квалификация — SDR Маша. Демо ведут 2 sales — Дима и Олег. Закрытие — "
            "Иван (head of sales). Еженедельный pipeline-обзор в понедельник 10:00, "
            "стенограмма в Notion."
        ),
        why_we_ask="Воронка в голове = воронки нет. Хотим увидеть «инструмент + регулярность».",
    ),
    CheckupQuestion(
        key="f2_stage_conversion",
        layer="sales", order=7,
        text="Конверсия по этапам за 90 дней: лиды → демо → договор. Цифры.",
        min_chars=120, min_words=20,
        expects=("3 цифры конверсии", "период", "сегментация (если есть)"),
        example_good=(
            "За 90 дней: лиды 800 → демо 120 (15%) → договор 18 (15% от демо, 2.25% сквозная). "
            "По сегменту marketing-agency: 22% демо→договор, 4% сквозная. "
            "По SMB SaaS: 8% демо→договор."
        ),
        why_we_ask="Без цифр конверсии любое решение по росту — гадание.",
    ),
    CheckupQuestion(
        key="f3_acv_cycle_cac",
        layer="sales", order=8,
        text="Средний чек, средний цикл сделки, CAC по двум главным сегментам.",
        min_chars=120, min_words=20,
        expects=("AOV", "цикл сделки в днях", "CAC", "сегмент"),
        example_good=(
            "Marketing-agency: AOV 280к, цикл 32 дня, CAC 45к (LTV/CAC ≈ 6). "
            "B2B SaaS: AOV 420к, цикл 58 дней, CAC 70к (LTV/CAC ≈ 5)."
        ),
        why_we_ask="Эти 3 числа определяют, в какой сегмент идём масштабироваться.",
    ),
    CheckupQuestion(
        key="f4_sources_cost",
        layer="sales", order=9,
        text="Источники лидов и стоимость по каждому за последний квартал.",
        min_chars=120, min_words=20,
        expects=("≥3 источника", "доля или объём", "CAC по источнику"),
        example_good=(
            "Outbound LinkedIn (Apollo) — 40% лидов, CAC 80к. Inbound с сайта (SEO+ABM) — "
            "25%, CAC 35к. Партнёрки — 20%, CAC 15к (реф 10%). Ивенты — 15%, CAC 120к."
        ),
        why_we_ask="Чтобы понять, какие каналы вы недоинвестируете, а какие — лишние.",
    ),
    CheckupQuestion(
        key="f5_bottleneck",
        layer="sales", order=10,
        text="Узкое место в воронке прямо сейчас — что мешает 2× росту?",
        min_chars=120, min_words=25,
        expects=("конкретный этап", "симптомы", "гипотеза причины"),
        example_good=(
            "Демо → договор для Enterprise: 8% против 18% по SMB. Симптом: решения "
            "принимают комитеты, им нужен ROI-кейс с цифрой. Гипотеза: нет публичных "
            "Enterprise-кейсов и кейса с CFO в роли buyer'а."
        ),
        why_we_ask="3 действия на следующую неделю мы выводим именно из узкого места.",
    ),

    # ===== OPERATIONS (5) =====
    CheckupQuestion(
        key="o1_load",
        layer="operations", order=11,
        text="Загрузка ключевых ролей за последний месяц и план на следующий (в часах).",
        min_chars=120, min_words=20,
        expects=("≥3 роли", "часы факт", "часы план или норма"),
        example_good=(
            "Tech-lead: 168/160ч (перегруз 5%). Senior dev #1: 140/160 (норма). "
            "Senior dev #2: 175/160 (перегруз 9%). CEO: 200/160 (хронический перегруз 25% — "
            "расфокус на operations, об этом подробнее в O3)."
        ),
        why_we_ask="Без часов загрузка обсуждается «по ощущениям» — это съедает маржу и людей.",
    ),
    CheckupQuestion(
        key="o2_project_margin",
        layer="operations", order=12,
        text="Маржа по 3 крупнейшим проектам/клиентам за квартал (выручка, прямые косты, маржа).",
        min_chars=150, min_words=25,
        expects=("3 объекта", "выручка", "прямые косты", "маржа %"),
        example_good=(
            "Клиент A: выручка 1.2М, прямые косты 480к, маржа 60%. "
            "Клиент B: 800к, 520к, маржа 35% — лимит. "
            "Клиент C: 600к, 240к, маржа 60%."
        ),
        why_we_ask="Среднее по портфелю врёт — нужны конкретные проекты с цифрами.",
    ),
    CheckupQuestion(
        key="o3_bottleneck",
        layer="operations", order=13,
        text="Главное узкое место в операциях и сколько вы теряете на нём в ₽/мес.",
        min_chars=120, min_words=25,
        expects=("процесс", "симптом", "ущерб в ₽ или часах"),
        example_good=(
            "Onboarding клиентов завязан на CEO (8ч на клиента). При 4 онбордингах в "
            "месяц — 32ч CEO ≈ 160к стоимости + блокирует стратегические задачи. "
            "Передача в playbook за 2 недели — экономия 130к/мес."
        ),
        why_we_ask="Узкое место можно посчитать в деньгах — это превращает «надо переделать» в проект.",
    ),
    CheckupQuestion(
        key="o4_decisions",
        layer="operations", order=14,
        text="Как принимаются операционные решения в команде? Регулярность, формат, документация.",
        min_chars=120, min_words=25,
        expects=("ритм встреч", "формат", "документация"),
        example_good=(
            "Еженедельный 60-мин sync в понедельник 10:00. Тактика — отдельно по каждой "
            "роли с CEO. Решения 250к+ — голосование с CFO/CTO. Документация — Notion, "
            "ADR-шаблон, ретроспектива раз в 2 недели."
        ),
        why_we_ask="Если решения принимает только CEO — это потолок роста.",
    ),
    CheckupQuestion(
        key="o5_next_90_days",
        layer="operations", order=15,
        text="3 главных действия по операционке на следующие 90 дней.",
        min_chars=120, min_words=25,
        expects=("3 действия", "ответственный", "deadline"),
        example_good=(
            "1) Снять CEO с onboarding'а: playbook + Маша (delivery) — до 1 июля. "
            "2) Внедрить трекинг часов по проектам в Toggl — Senior dev, до 15 июня. "
            "3) Переделать маржинальную сводку: автоматический отчёт раз в неделю — CFO, до 1 августа."
        ),
        why_we_ask="Это то, по чему мы потом сверим прогресс на 90-дневной отметке.",
    ),

    # ===== MONEY (5) =====
    CheckupQuestion(
        key="m1_cashflow",
        layer="finance", order=16,
        text="Cash на 90 дней вперёд: остаток сегодня, поступления, платежи, прогноз на конец.",
        min_chars=120, min_words=25,
        expects=("остаток сегодня", "поступления", "платежи", "прогноз 90 дн"),
        example_good=(
            "Сегодня 4.8М. Подтверждённые поступления +6.2М (договоры с предоплатой). "
            "Платежи 7.1М (ФОТ 4.6М, налоги 1.2М, аренда 0.4М, маркетинг 0.9М). "
            "Прогноз на конец 90 дней: 3.9М — это меньше 1.5х месячных платежей, флаг."
        ),
        why_we_ask="Cash на ≥90 дней — базовая страховка собственника.",
    ),
    CheckupQuestion(
        key="m2_ebitda",
        layer="finance", order=17,
        text="EBITDA и маржа по компании за последние 12 месяцев (с учётом налогов).",
        min_chars=120, min_words=20,
        expects=("выручка", "EBITDA", "маржа %", "налоговый режим"),
        example_good=(
            "Выручка 78М, операционные расходы 60М, налог УСН 6% — 4.7М. "
            "EBITDA после налогов 13.3М, маржа 17%. Режим — УСН доходы."
        ),
        why_we_ask="Без EBITDA после налогов решения по росту опираются на иллюзию маржи.",
    ),
    CheckupQuestion(
        key="m3_vat_2026",
        layer="finance", order=18,
        text="НДС-2026 / антидробление: какой сценарий вы выбрали и почему?",
        min_chars=120, min_words=25,
        expects=("текущий режим", "лимит", "выбранный сценарий", "обоснование"),
        example_good=(
            "Сейчас УСН без НДС, оборот 78М. К 2027 пробьём 90М лимит — пересмотрели "
            "вместе с бухгалтером, выбрали УСН с НДС 5% (без вычетов). Допнагрузка "
            "≈ 2.8М/год, проще админить, чем ОСНО. Дробление не рассматривали — "
            "репутация и FNS-риски выше экономии."
        ),
        why_we_ask="Май 2026 — переходное окно. Решение влияет на цены на весь следующий год.",
    ),
    CheckupQuestion(
        key="m4_reserves",
        layer="finance", order=19,
        text="Резерв и доступное финансирование: чем закроете 3 плохих месяца?",
        min_chars=120, min_words=20,
        expects=("резерв в ₽", "кредитная линия", "сценарий сокращения"),
        example_good=(
            "Резерв 6М на отдельном счёте (1.3 месяца ФОТ). Кредитная линия 8М с "
            "Точкой под 22%. План при cash < 4М: сокращаем маркетинг на 30%, "
            "замораживаем найм, переходим на квартальный ФОТ-обзор."
        ),
        why_we_ask="Финансовая устойчивость = резерв + план Б.",
    ),
    CheckupQuestion(
        key="m5_decisions_90",
        layer="finance", order=20,
        text="3 ключевых финансовых решения на ближайшие 90 дней.",
        min_chars=120, min_words=25,
        expects=("3 решения", "сроки", "ответственный"),
        example_good=(
            "1) Перейти на УСН с НДС с июля — закрепить с бухгалтерией до 20 июня (CFO). "
            "2) Повысить цены контрактов на 15% — переподписать топ-5 клиентов до конца Q3 (Иван). "
            "3) Закрыть минусовый продуктовый поток (-300к/мес) — до 1 сентября (CEO + CFO)."
        ),
        why_we_ask="90-дневный план денежных решений — основной артефакт Чекапа.",
    ),
)


# --------------- F2: VAT zone detection ---------------

VAT_ZONE_BELOW = "below_threshold"
VAT_ZONE_APPROACHING = "approaching"
VAT_ZONE_FIRST_TIME = "first_time"
VAT_ZONE_ESTABLISHED = "established"

_VAT_DESCRIPTIONS = {
    VAT_ZONE_BELOW: (
        "Вне зоны НДС-реформы 2026 — пока на УСН без НДС. "
        "Следите за динамикой выручки: порог снижается до 15 млн в 2027 году."
    ),
    VAT_ZONE_APPROACHING: (
        "В зоне риска на горизонте 2–3 лет. "
        "С 2027 порог снижается до 15 млн ₽, с 2028 — до 10 млн ₽. "
        "Подготовьте учётную систему и проконсультируйтесь с бухгалтером заранее."
    ),
    VAT_ZONE_FIRST_TIME: (
        "Впервые в 2026 году попадаете в НДС-учёт. "
        "Это центральный риск-фактор для вашего бизнеса. "
        "Необходимо выбрать ставку (5% без вычетов или 20% с вычетами), "
        "обновить договоры и настроить фискальный учёт до 01.01.2026."
    ),
    VAT_ZONE_ESTABLISHED: (
        "Уже работаете с НДС. Реформа 2026 для вас процедурная, не структурная. "
        "Проверьте договоры с контрагентами на УСН — им теперь нужны СФ."
    ),
}

_VAT_ADVICE = {
    VAT_ZONE_BELOW: "Продолжайте отслеживать выручку. Если приближаетесь к 15 млн — начните подготовку за 6 месяцев.",
    VAT_ZONE_APPROACHING: "Рекомендуем: встреча с бухгалтером в Q3 2026, выбор учётной системы с поддержкой НДС, обновление шаблонов договоров.",
    VAT_ZONE_FIRST_TIME: (
        "🔴 Срочно: (1) определите ставку НДС, (2) обновите договоры, "
        "(3) подключите онлайн-кассу с НДС, (4) уведомите топ-клиентов."
    ),
    VAT_ZONE_ESTABLISHED: "Проверьте контрагентов на УСН — проведите аудит договорной базы на предмет НДС-корректности.",
}


def determine_vat_zone(answer_text: str) -> dict:
    """Определяет зону риска по НДС-реформе 2026 на основе текста ответа.

    Работает с ответом на вопрос m2_ebitda (выручка) или m3_tax (налоговый режим).
    Возвращает dict с ключами: zone, description, advice.
    """
    t = answer_text.lower()

    # Числовые паттерны: ищем упоминание миллионов рублей
    def _extract_millions(text: str) -> float | None:
        import re
        # Ищем паттерн "NNN млн" или "NNN M" или "NNNM руб"
        patterns = [
            r"(\d[\d\s]*)\s*млн",
            r"(\d[\d\s]*)\s*m\b",
            r"(\d+)\s*000\s*000",  # 60 000 000
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                raw = m.group(1).replace(" ", "")
                try:
                    return float(raw)
                except ValueError:
                    pass
        return None

    rev = _extract_millions(t)

    if rev is not None:
        if rev < 10:
            zone = VAT_ZONE_BELOW
        elif rev < 20:
            zone = VAT_ZONE_APPROACHING
        elif rev < 60:
            zone = VAT_ZONE_FIRST_TIME
        else:
            zone = VAT_ZONE_ESTABLISHED
        return {"zone": zone, "description": _VAT_DESCRIPTIONS[zone], "advice": _VAT_ADVICE[zone]}

    # Текстовые маркеры (если цифры не нашли)
    if any(k in t for k in ("усн с ндс", "осно", "ндс 20%", "ндс 5%", "плательщик ндс", "с ндс")):
        zone = VAT_ZONE_ESTABLISHED
    elif any(k in t for k in ("60", "80", "100", "150", "200", "свыше 60", "больше 60", "> 60")):
        zone = VAT_ZONE_ESTABLISHED
    elif any(k in t for k in ("20", "30", "40", "50", "20-60", "20–60", "30–60")):
        zone = VAT_ZONE_FIRST_TIME
    elif any(k in t for k in ("10", "15", "10-20", "10–20")):
        zone = VAT_ZONE_APPROACHING
    else:
        zone = VAT_ZONE_BELOW

    return {"zone": zone, "description": _VAT_DESCRIPTIONS[zone], "advice": _VAT_ADVICE[zone]}


def by_layer() -> dict[str, list[CheckupQuestion]]:
    out: dict[str, list[CheckupQuestion]] = {
        "strategy": [], "sales": [], "operations": [], "finance": []
    }
    for q in CHECKUP_QUESTIONS:
        out[q.layer].append(q)
    return out


def by_key() -> dict[str, CheckupQuestion]:
    return {q.key: q for q in CHECKUP_QUESTIONS}
