# ТЗ · Mini-Чекап v2.0 · бот @edl_os_bot + сайт elephantdreams.ru

> **Версия:** v2.0
> **Дата:** 21.05.2026
> **Статус:** черновик к разработке, готов к загрузке в новый чат
> **Источники канона:** `EDL_Session_Summary_21052026.md` §1.1 / §1.2 / §1.4 / §1.5 / §1.6 / §1.7 (Mini), §2.4, §3.2.8, §3.3, §3.4.1
> **Заменяет:** `BOT_TZ.md §7.2`, текущий `/quiz` бота (12 вопросов «старого» поколения), `quiz.html` (6 вопросов), `js/mini-checkup.js` (5 вопросов в виджете)
> **Не трогает в этом ТЗ:** Чекап/Чекап Plus (отдельное ТЗ `TZ_checkup_plus_v2.md`), Диагностику, Спринт, MCP-сервер

---

## 0. Карта документа

1. Цель и место Mini-Чекапа в воронке
2. Текущее состояние (что уже есть в коде)
3. Канон Mini-Чекапа (источник правды — §1.7 SoT)
4. Опросник: 2 предварительных + 12 основных вопросов
5. Формула Score со stage-relative весами
6. Матрица бенчмарков 6 сегментов × 4 стадии
7. Логика выдачи результата (Score + бенчмарк + 3 точки роста)
8. ТЗ на бота `/quiz`
9. ТЗ на сайт: страница `quiz.html` + виджет `js/mini-checkup.js`
10. Связка «виджет/сайт ↔ бот» (deep-link с переносом ответов)
11. Изменения БД
12. API контракты (FastAPI)
13. Аналитика и события
14. Тестирование
15. Acceptance criteria и roll-out
16. Что вне скоупа

---

## 1. Цель Mini-Чекапа и место в воронке

**Wedge продукта.** Mini-Чекап = бесплатная low-friction точка входа. Цели:

1. Фаундер за **4–7 минут** (медиана; в маркетинге заявляем «15 мин», чтобы не отпугнуть глубиной) получает **Founder OS Score 0–100** + сравнение с сегментом × стадией + **3 точки роста**.
2. Мы получаем: контакт (опционально), сегмент, стадию роста, Score, **базу для персонализации Чекапа** (не переспрашиваем эти данные).
3. Конверсия Mini → Чекап Base/Plus — целевая **5–10%** (см. SoT §2.4).

**Принципиальная разница со старым `/quiz`:**

| | Старый `/quiz` (BOT_TZ.md §7.2) | Mini-Чекап v2.0 |
|---|---|---|
| Вопросов | 12 одним списком | **2 предварительных + 12 основных** |
| Score | сумма / 120 × 100, равные веса | **взвешенное среднее** 4 слоёв с весами по стадии |
| Бенчмарк | нет | **сравнение с сегментом × стадией** (6×4 матрица) |
| Точки роста | recommendation по диапазону Score | **3 точки роста**, выведенные из слабых слоёв |
| Канон слоёв | strategy/sales/operations/finance | **01 Стратегия / 02 Воронка / 03 Операционка / 04 Деньги** (явные коды) |
| Stage detection | нет | **по команде + выручке** (гибрид Greiner) |
| Surface | только бот | **виджет на сайте + страница `quiz.html` + бот** |

---

## 2. Текущее состояние (что уже есть)

### 2.1 Бот

- `edl-os-bot/src/core/quiz.py` — 12 вопросов, `total_score()`, `layer_scores()`, `recommendation()`.
- `edl-os-bot/src/bot/handlers/quiz.py` — handler `/quiz`, FSM через `context.user_data`, кнопки `quiz:ans:<idx>`.
- Поле `User.quiz_score: int | None` — есть.
- Поля `User.company_size`, `User.company_revenue_range` — есть, но не заполняются из quiz.
- События в `events` — не пишутся для quiz (нужно добавить).

### 2.2 Сайт

- `quiz.html` — 6 вопросов, multi-step форма, прогресс-бар, **не отдаёт результат**, ведёт в бот.
- `js/mini-checkup.js` (539 строк) — самостоятельный диалоговый виджет с 5 вопросами и keyword-based follow-up. Раскрывается по триггеру `bot-widget.js`.
- Триггер виджета — `js/bot-widget.js` (cumulative trigger 30 сек / 30% scroll, cookie на 7 дней).

### 2.3 Что выкидываем / переписываем

- ✗ `js/mini-checkup.js` — переписываем целиком (15-минутный диалог → 4–7 мин с 12 вопросов).
- ✗ `quiz.html` — переписываем целиком (6 → 14 вопросов = 2+12, с результатом и переходом в бот).
- ✗ `edl-os-bot/src/core/quiz.py` — заменяем `QUIZ_QUESTIONS`, переписываем `total_score`, `recommendation`, добавляем `stage_detection`, `benchmark`, `growth_points`.
- ✓ `quiz.py` handler оставляем по структуре (FSM 1 вопрос за раз), но дописываем обработку 2 предварительных + рендеринг нового результата.

---

## 3. Канон Mini-Чекапа

**Источник правды:** `EDL_Session_Summary_21052026.md` §1.7.

### 3.1 Параметры

- **12 основных вопросов** = по 3 на каждый слой (01–04).
- **Преимущественно multiple-choice** (5 вариантов, в виджете-friendly формате).
- **2 предварительных вопроса** (команда, сегмент) — нужны для определения стадии и бенчмарка.
- **4–7 минут реально**, «15 мин в маркетинге» — заявляем на сайте, чтобы не давить ожиданием.
- **На выходе:** Score + benchmark (сегмент × стадия) + 3 точки роста + CTA на Чекап.

### 3.2 Канон 4 слоёв (SoT §1.1)

| Код | Название | Что измеряем (Mini-уровень) |
|---|---|---|
| **01** | **Стратегия** (Направление) | горизонт 3 лет, фокус года, что НЕ делаем |
| **02** | **Воронка** (Клиенты) | где живёт воронка, конверсия, цикл сделки |
| **03** | **Операционка** (Процессы) | загрузка команды, узкое горлышко, ритм |
| **04** | **Деньги** (Финансы) | маржа компании, cash 30 дней, НДС-2026 |

> Используем **только** эти 4 слоя + коды. Никаких «strategy/sales/operations/finance» в копирайте — только в коде.

### 3.3 Канон стадий (SoT §1.4)

| Стадия | Команда | Выручка/год | Триггер |
|---|---|---|---|
| **Старт** | 1–10 | до 15 М ₽ | Кризис лидерства |
| **Команда** | 10–25 | 15–60 М ₽ | Кризис автономии — НДС-2026 |
| **Структура** | 25–50 | 60–200 М ₽ | Кризис координации |
| **Зрелость** | 50+ | 200 М+ ₽ | Переход к среднему |

### 3.4 Канон сегментов (SoT §1.6)

`edu` Онлайн-школа · `mp` Маркетплейс · `it` IT/агентство · `prod` Производство/опт · `serv` Услуги · `saas` B2B SaaS.

---

## 4. Опросник Mini-Чекапа v2

### 4.1 Предварительные вопросы (P0 — Pre)

Цель: определить **сегмент** и **стадию** для весов Score + бенчмарка. Если фаундер пришёл из бота и эти поля уже заполнены — **не переспрашиваем** (пропускаем напрямую к Q1).

#### P1 · Сегмент бизнеса

> **Какой у вас сегмент?**
> ⬡ Онлайн-школа / EdTech `edu`
> ⬡ Маркетплейс / e-commerce `mp`
> ⬡ IT / digital-агентство / разработка `it`
> ⬡ Производство / опт / B2B-поставки `prod`
> ⬡ Услуги (консалтинг, юр-, бух-, медицина) `serv`
> ⬡ B2B SaaS / подписочный продукт `saas`
> ⬡ Другое `other` → дальше работает без бенчмарка («ваш сегмент в калибровке»)

Сохраняем в `users.segment`.

#### P2 · Размер команды и выручка

Один вопрос, шесть кортежей **«команда · выручка»** — лестница комбинаций. Покрывает 4 стадии без двух отдельных вопросов:

> **Сколько у вас людей и какая выручка за прошлый год?**
> ⬡ 1–10 чел · до 15 М ₽ → `start`
> ⬡ 10–25 чел · 15–60 М ₽ → `team`
> ⬡ 25–50 чел · 60–200 М ₽ → `structure`
> ⬡ 50+ чел · 200 М+ ₽ → `maturity`
> ⬡ Команда меньше, чем выручка предполагает (например, 5 чел · 100 М) → `outlier_small_team`, стадия = по выручке
> ⬡ Команда больше, чем выручка предполагает (30 чел · 20 М) → `outlier_big_team`, стадия = по команде

Сохраняем:
- `users.company_size` (берём верхнюю границу диапазона: 10/25/50/100)
- `users.company_revenue_range` (`<15M | 15-60M | 60-200M | 200M+`)
- определяем `stage` ∈ `{start, team, structure, maturity}` (см. §5.1)

### 4.2 12 основных вопросов

Шкала: 0/3/5/8/10 (5 опций). Каждый вопрос — 1 слой. По 3 вопроса на слой. Один-в-один **multiple-choice**, без свободного ввода (это разница со старым `/quiz`, который уже multiple-choice — но многие формулировки устарели и пересматриваются).

> **Принцип формулировок Mini:** одна короткая ситуация → 5 опций от «не думал» до «автоматизировано». Никаких чисел в ответ — это для Чекапа. Mini показывает зрелость инфраструктуры/мышления, не точные метрики.

#### Слой 01 · Стратегия

| Key | 1/12 (Q1) — горизонт |
|---|---|
| `s1_horizon_3y` | **«У вас есть 3-летняя картина: продукт, выручка, команда?»** |
| | 0 — «Не думал так далеко» |
| | 3 — «Есть смутный образ» |
| | 5 — «Есть 1–2 ставки, без цифр» |
| | 8 — «3 ставки и метрики по ним» |
| | 10 — «Записано, согласовано, ежеквартально пересматриваю» |

| Key | 2/12 (Q2) — фокус |
|---|---|
| `s2_year_focus` | **«Фокус года — есть и понятен команде?»** |
| | 0 — «Фокуса нет, делаем всё подряд» |
| | 3 — «Фокус знаю я, команда — не очень» |
| | 5 — «Озвучивал, но без документа» |
| | 8 — «Один документ, синхрон раз в квартал» |
| | 10 — «Каждый сотрудник назовёт фокус года» |

| Key | 3/12 (Q3) — что не делаем |
|---|---|
| `s3_not_doing` | **«Понимаете, что НЕ делать в этом году?»** |
| | 0 — «Беремся за всё, что приходит» |
| | 3 — «Иногда отказываю, без правила» |
| | 5 — «Есть негласные критерии» |
| | 8 — «Есть явный список “не делаем”» |
| | 10 — «Список — часть стратегии, команда сверяется» |

#### Слой 02 · Воронка

| Key | 4/12 — где живёт воронка |
|---|---|
| `f1_pipeline_home` | **«Где живёт ваша воронка продаж?»** |
| | 0 — «В голове / в переписках» |
| | 3 — «Excel/Sheets, обновляю редко» |
| | 5 — «CRM, дисциплина средняя» |
| | 8 — «CRM + регулярный обзор» |
| | 10 — «CRM + автосводка + конверсии по этапам» |

| Key | 5/12 — конверсия |
|---|---|
| `f2_conv_demo_deal` | **«Конверсия из заявки в договор — знаете?»** |
| | 0 — «Не считаю» · 3 — «Примерно на глаз» · 5 — «Общую знаю» · 8 — «По сегментам» · 10 — «По сегментам и продавцу» |

| Key | 6/12 — цикл сделки |
|---|---|
| `f3_deal_cycle` | **«Средний цикл сделки в днях?»** |
| | 0 — «Не знаю» · 3 — «Обычно столько-то» · 5 — «Считал руками» · 8 — «Знаю и трекаю» · 10 — «Знаю и вижу, где застревает» |

#### Слой 03 · Операционка

| Key | 7/12 — загрузка |
|---|---|
| `o1_team_load` | **«Загрузка команды — что у вас с этим?»** |
| | 0 — «Не считаю, все “вроде заняты”» · 3 — «На глаз» · 5 — «Раз в пару месяцев» · 8 — «Регулярная сводка по часам» · 10 — «Загрузка считается автоматически, узкие места заранее» |

| Key | 8/12 — узкое горлышко |
|---|---|
| `o2_bottleneck` | **«Узкое горлышко в доставке — известно?»** |
| | 0 — «Не знаю» · 3 — «Догадываюсь» · 5 — «Знаю, не системно» · 8 — «Работаю с ним» · 10 — «Решено, узкое место сместилось дальше» |

| Key | 9/12 — ритм |
|---|---|
| `o3_rhythm` | **«Есть ли у бизнеса недельный/месячный ритм встреч и сводок?»** |
| | 0 — «Ритма нет» · 3 — «Встречаемся когда горит» · 5 — «Недельная планёрка» · 8 — «Недельный + месячный ритм с метриками» · 10 — «Daily/weekly/monthly синхронизованы, агенты пишут сводки» |

> Замечание: в старом `/quiz` слой Операционки покрывал `team_load / margin_by_project / bottleneck`. Маржу-по-проектам убираем из Mini — это вопрос Чекапа. Вместо неё — **ритм** (новый, по канону §1.2 «РИТМ-АГЕНТ»).

#### Слой 04 · Деньги

| Key | 10/12 — маржа компании |
|---|---|
| `m1_company_margin` | **«Маржа по компании в целом — знаете цифру?»** |
| | 0 — «Нет» · 3 — «Очень примерно» · 5 — «Раз в квартал» · 8 — «Каждый месяц» · 10 — «Каждый месяц + понимаю, что её двигает» |

| Key | 11/12 — cash |
|---|---|
| `m2_cash_30d` | **«Cash на 30 дней вперёд — видите?»** |
| | 0 — «Нет» · 3 — «Считаю руками когда тревожно» · 5 — «Sheets, обновляю раз в месяц» · 8 — «Сводка регулярно» · 10 — «Cash на 90 дней с поступлениями/платежами на одном экране» |

| Key | 12/12 — НДС-2026 |
|---|---|
| `m3_vat_2026` | **«НДС-2026 / антидробление — есть понятная картина?»** |
| | 0 — «Тревожно, не понимаю» · 3 — «Слышал, не считал» · 5 — «Считал с бухгалтером» · 8 — «Есть финансовая модель сценариев» · 10 — «Решение принято, действуем по плану» |

### 4.3 Замечания по копирайту

- **Все вопросы — на «вы».** Не «фаундер», не «собственник» — обращаемся напрямую.
- **Никаких аббревиатур** (CAC/LTV/MRR) в Mini — это для Чекапа. Mini читается без специальных знаний.
- **Опции одной длины** в пределах вопроса (нельзя «Нет» рядом с длинной формулировкой) — выравниваем визуально.
- Текущие опции `/quiz` в `core/quiz.py:24-172` — **частично переиспользуем** (фокус, не-делаем, cash, vat, margin), но обновляем нумерацию и добавляем недостающие (ритм, горизонт-3-лет, конверсия-демо).

---

## 5. Формула Score (stage-relative readiness)

**Источник:** SoT §1.5.

### 5.1 Определение стадии (`stage_detection`)

Из ответа P2:

```python
STAGE_FROM_P2 = {
    "start":      ("1-10",   "<15M",     "start"),
    "team":       ("10-25",  "15-60M",   "team"),
    "structure":  ("25-50",  "60-200M",  "structure"),
    "maturity":   ("50+",    "200M+",    "maturity"),
}

# Outliers (расхождение команда vs выручка)
def resolve_outlier(option: str, team_label: str | None, revenue_label: str | None) -> str:
    if option == "outlier_small_team":  # «5 чел · 100 М»
        # стадия определяется по выручке (бизнес capital-light)
        return stage_by_revenue(revenue_label)  # 100M → structure
    if option == "outlier_big_team":     # «30 чел · 20 М»
        # стадия определяется по команде (бизнес labor-heavy)
        return stage_by_team(team_label)        # 30 → structure
    raise ValueError
```

Если outlier выбран без явного team/revenue (мы не спрашиваем точные числа в Mini) — **по умолчанию ставим `team` для small_team и `structure` для big_team** и помечаем `stage_confidence='low'` (показываем в результате plate «уточним на Чекапе»).

### 5.2 Веса слоёв по стадии

| Слой | Старт | Команда | Структура | Зрелость |
|---|---:|---:|---:|---:|
| 01 Стратегия | 0.35 | 0.30 | 0.25 | 0.30 |
| 02 Воронка | 0.25 | 0.30 | 0.25 | 0.20 |
| 03 Операционка | 0.15 | 0.20 | **0.30** | 0.30 |
| 04 Деньги | 0.25 | 0.20 | 0.20 | 0.20 |

> Сумма по столбцу = 1.0.

### 5.3 Расчёт

```python
def layer_score_0_100(answers: dict[str, int], layer: str) -> float:
    """3 вопроса по слою × 10 баллов max = 30 → шкалируем к 0..100"""
    qs = [q for q in QUIZ_QUESTIONS if q.layer == layer]
    raw = sum(answers.get(q.key, 0) for q in qs)
    return raw * 100 / (10 * len(qs))   # / 30 * 100

def total_score(answers, stage: str) -> int:
    weights = STAGE_WEIGHTS[stage]  # dict layer→weight
    total = sum(layer_score_0_100(answers, L) * weights[L] for L in ("01","02","03","04"))
    return round(total)
```

**Важная семантика для UI:** один и тот же бизнес после перехода `team → structure` теряет 10–20% Score при тех же ответах — планка выросла. Это правильно. В тексте результата если у юзера `stage='structure'` и слабый Operations — показываем плашку *«В стадии Структура планка по операционке выше — мы знаем»*.

### 5.4 Категории Score (для копирайта результата)

| Диапазон | Лейбл | Цвет |
|---|---|---|
| 0–40 | «Бизнес держится на вас лично» | red |
| 41–60 | «Есть базовая структура, много пробелов» | orange |
| 61–75 | «Зрелая инфраструктура, но узкие места видны» | yellow |
| 76–100 | «Готовая к масштабированию операционная база» | green |

---

## 6. Матрица бенчмарков

**Источник:** SoT §1.6. Точная калибровка — после 100+ клиентов. Сейчас захардкоженные приближённые значения.

```python
BENCHMARK = {
    # segment: {stage: mean_score}
    "edu":  {"start": 48, "team": 54, "structure": 62, "maturity": 71},
    "mp":   {"start": 45, "team": 58, "structure": 65, "maturity": 72},
    "it":   {"start": 52, "team": 56, "structure": 60, "maturity": 68},
    "prod": {"start": 42, "team": 50, "structure": 58, "maturity": 70},
    "serv": {"start": 46, "team": 52, "structure": 58, "maturity": 66},
    "saas": {"start": 50, "team": 58, "structure": 64, "maturity": 73},
}
SEGMENT_LABEL = {
    "edu": "онлайн-школ", "mp": "маркетплейсов", "it": "IT-агентств",
    "prod": "производств/опта", "serv": "услуг", "saas": "B2B SaaS",
}
STAGE_LABEL = {"start": "Старт", "team": "Команда", "structure": "Структура", "maturity": "Зрелость"}
```

### 6.1 Копирайт в результате

```
Ваш Score: 67
Средний для онлайн-школ на стадии Команда: 54
Δ +13 — вы выше среднего по сегменту
```

Если сегмент = `other` или калибровки нет (мало клиентов в сегменте × стадии — отслеживаем флагом):

```
Ваш Score: 67
Бенчмарк по вашему сегменту мы пока калибруем (нужно ≥30 клиентов).
Доступная медиана по всем сегментам на стадии Команда: 55.
```

### 6.2 Хранение и обновление

- Хардкод сейчас в `core/benchmarks.py` (новый файл).
- К Q3 2026 — заменить на чтение из таблицы `benchmark_segment_stage` (см. §11), которая считается ежемесячно через Celery beat task `update_benchmarks` (агрегация `quiz_score` по `segment × stage`, исключая outlier-stages).

---

## 7. Логика выдачи результата

### 7.1 Состав результата

1. **Score 0–100** (большая цифра, цвет по §5.4)
2. **Лейбл категории**
3. **Стадия роста** (с пометкой outlier если есть)
4. **Бенчмарк** (§6.1)
5. **4 слоя — мини-плитки** с Score по слою (0–100) и цветом-светофором (≥75 зелёный, 50–74 жёлтый, <50 красный)
6. **3 точки роста** (см. §7.2)
7. **CTA: Чекап Base за 9 000 ₽ / Чекап Plus за 14 000 ₽** + deep-link `/start audit` или `/start audit_plus`
8. **Микро-копия:** «За 24 часа после оплаты — PDF 10–15 стр + FigJam-карта»

### 7.2 Алгоритм «3 точки роста»

```python
def top3_growth_points(answers, stage) -> list[GrowthPoint]:
    # 1. Считаем layer_score_0_100 для каждого слоя
    # 2. Сортируем по возрастанию (самый слабый — первый)
    # 3. Для каждого из топ-3 слабых слоёв — берём 1 вопрос с минимальным ответом
    #    и достаём из словаря GROWTH_HINTS[question_key] человеческий совет
    # 4. Если 2+ вопроса с одинаковым min — выбираем тот, у которого выше «вес продвижения»
    #    (priority_for_stage[layer][question_key])
```

#### GROWTH_HINTS (черновик)

Для каждого `question_key` — 2 варианта совета: для оценки 0–3 и для оценки 5–8. Пример:

| key | range 0–3 | range 5–8 |
|---|---|---|
| `s1_horizon_3y` | «Зафиксируйте картину через 3 года в одном документе: продукт, выручка, команда. 1 час работы.» | «Добавьте 2–3 численные метрики к каждой ставке, чтобы видеть прогресс.» |
| `s2_year_focus` | «Сформулируйте фокус года одной фразой и проверьте, что 5 человек из команды его назовут.» | «Внедрите квартальный ритм синхронизации фокуса.» |
| `f1_pipeline_home` | «Перенесите воронку в CRM (Bitrix, amoCRM или Pipedrive) за неделю — без неё нельзя считать конверсии.» | «Настройте автосводку по этапам и дайте РОПу/себе еженедельный обзор.» |
| `f2_conv_demo_deal` | «Один раз руками посчитайте: сколько демо за квартал × сколько договоров. Это даст базовую конверсию.» | «Разложите конверсию по сегментам — обычно есть 1–2, где она вдвое выше.» |
| `o1_team_load` | «Раз в месяц снимайте загрузку команды по часам — даже грубая таблица лучше, чем ничего.» | «Настройте автосчёт загрузки в Toggl/Asana/Notion, чтобы видеть узкие места заранее.» |
| `o3_rhythm` | «Запустите недельную планёрку 30 мин с одним вопросом: «что мешает достичь фокуса года?»» | «Добавьте месячный ретро с разбором метрик слоя — это закрывает 80% разрывов.» |
| `m1_company_margin` | «Считайте маржу компании каждый месяц вручную — это базовый skill фаундера.» | «Раскладывайте маржу по 3–5 драйверам (себестоимость / ФОТ / прочие). Это покажет, что её двигает.» |
| `m2_cash_30d` | «Сделайте Sheets с поступлениями и платежами на 30 дней — самый простой шаг к финансовому контролю.» | «Удлините горизонт до 90 дней и добавьте сценарии (best/base/worst).» |
| `m3_vat_2026` | «Закажите консультацию у вашего бухгалтера: при текущей структуре — попадаете ли вы под порог 60 М ₽?» | «Постройте финансовую модель с 3 сценариями (с НДС / без НДС / дробление + риск).» |

(Полная таблица — в файле `edl-os-bot/src/core/growth_hints.py`, 12 ключей × 2 диапазона + дефолт.)

### 7.3 CTA-логика

| Score | Основной CTA | Вторичный CTA |
|---|---|---|
| 0–40 | **Чекап Base 9 000 ₽** | «Хочу сначала поговорить» → `/start demo` |
| 41–70 | **Чекап Plus 14 000 ₽** (видео-разбор от Кати как тизер Диагностики) | Чекап Base 9 000 ₽ |
| 71–100 | **Диагностика 45 000 ₽** (лист ожидания → `/start diagnostic_waitlist`) | Чекап Plus 14 000 ₽ как «снимок состояния» |

> Цены — единственная зона, где Mini-Чекап взаимодействует с продуктовой матрицей v1.0. Источник цен — `audit.py:AUDIT_AMOUNT_RUB / AUDIT_PLUS_AMOUNT_RUB`. Цены Диагностики/Спринта/Плана Роста не упоминаются числами в Mini, только названия.

---

## 8. ТЗ на бота: команда `/quiz`

### 8.1 Файлы к правке

| Файл | Что делаем |
|---|---|
| `src/core/quiz.py` | **Переписываем целиком**: `QUIZ_QUESTIONS`, `STAGE_WEIGHTS`, `STAGE_FROM_P2`, `total_score(answers, stage)`, `layer_score_0_100`, `stage_detection(p2_option, segment)`, `top3_growth_points(answers, stage)`, `category_label(score)`, `recommendation(score, stage, segment)` → возвращает структуру `MiniCheckupResult`. |
| `src/core/benchmarks.py` | **Новый файл**: `BENCHMARK`, `benchmark_for(segment, stage)` → `(mean: int, source: 'hardcoded' \| 'db')`. |
| `src/core/growth_hints.py` | **Новый файл**: `GROWTH_HINTS: dict[key, {low: str, mid: str}]` + `hint_for(question_key, answer_score)`. |
| `src/bot/handlers/quiz.py` | Дописываем: handler первых двух preliminary-вопросов (с пропуском, если `users.segment` и `users.company_size`+`company_revenue_range` уже заполнены); рендеринг результата по новой структуре; событие `mini_checkup_completed`. |
| `src/bot/keyboards.py` | Inline-клавиатуры для P1 (6 + «Другое» = 7 кнопок), P2 (6 опций), 12 вопросов (5 опций каждый), результат (3 CTA-кнопки). |
| `src/bot/texts.py` | Все user-facing строки. |
| `src/db/models.py` | + `User.quiz_completed_at: datetime \| None`, `User.quiz_stage: str \| None`. См. §11. |
| `src/db/repos.py` | Дописать `mark_quiz_completed(user_id, score, stage, segment, answers_jsonb)`. |
| `src/core/lead_stage.py` | По завершении Mini-Чекапа: `cold → warm`. |

### 8.2 FSM-состояния `/quiz`

`context.user_data[KEY_QUIZ_STATE]`:

| State | Что ждёт |
|---|---|
| `await_consent` | согласие на обработку ПД (если ещё не дано) |
| `await_p1_segment` | callback `quiz:p1:<seg>` |
| `await_p2_size_revenue` | callback `quiz:p2:<opt>` |
| `await_q1` … `await_q12` | callback `quiz:ans:<q_idx>:<score>` |
| `done` | результат показан, кнопки CTA активны |

**Skip-логика для P1/P2:** если `user.segment is not None` и `user.company_size is not None` → переходим напрямую на `await_q1`. Если только одно из двух есть — спрашиваем только недостающий.

### 8.3 Структуры

```python
# src/core/quiz.py
from typing import Literal
from dataclasses import dataclass

Layer = Literal["01", "02", "03", "04"]
Stage = Literal["start", "team", "structure", "maturity"]

@dataclass(slots=True, frozen=True)
class MiniQuestion:
    key: str
    layer: Layer
    order: int                # 1..12
    text: str                 # «1/12 · …»
    options: tuple[tuple[str, int], ...]   # 5 кортежей

@dataclass(slots=True, frozen=True)
class GrowthPoint:
    layer: Layer
    layer_label: str          # «Деньги»
    question_key: str
    short: str                # «Cash на 30 дней — не считается»
    action: str               # «Сделайте Sheets с поступлениями…»

@dataclass(slots=True, frozen=True)
class MiniCheckupResult:
    score: int                # 0..100
    category: str             # «Зрелая инфраструктура, но узкие места видны»
    category_color: Literal["red","orange","yellow","green"]
    stage: Stage
    stage_label: str          # «Команда»
    stage_confidence: Literal["high","low"]
    segment: str              # 'edu'
    segment_label: str        # 'онлайн-школ'
    layer_scores: dict[Layer, int]      # {01: 70, 02: 55, 03: 40, 04: 80}
    benchmark_mean: int | None
    benchmark_delta: int | None         # score - mean
    growth_points: tuple[GrowthPoint, GrowthPoint, GrowthPoint]
    cta_primary: Literal["audit","audit_plus","diagnostic_waitlist"]
    cta_secondary: Literal["audit","audit_plus","demo"]
```

### 8.4 Рендеринг результата в боте (3 сообщения)

> Telegram: одно сообщение ≤ 4096 символов. Бьём на 3 сообщения для дыхания + последнее с inline-клавиатурой.

**Сообщение 1 — Score & бенчмарк:**

```
🎯 Founder OS Score · *67/100*

Зрелая инфраструктура, но узкие места видны.

Стадия роста: *Команда* (10–25 чел · 15–60 М ₽)
Сегмент: онлайн-школа

Средний по онлайн-школам на стадии Команда: 54
Δ +13 — вы выше среднего по сегменту.

_Бенчмарк калибруется — точнее после 100+ клиентов в каждой стадии × сегменте._
```

**Сообщение 2 — 4 слоя:**

```
*Срез по слоям* (0–100, чем выше — тем зрелее):

🟢 01 · Стратегия — 80
🟡 02 · Воронка — 55
🔴 03 · Операционка — 40
🟢 04 · Деньги — 75

Самый слабый слой — Операционка. На стадии Команда это типовой кризис автономии: команда выросла, регулярного ритма ещё нет.
```

**Сообщение 3 — 3 точки роста + CTA:**

```
*3 точки роста на ближайшие 30 дней:*

1. *Ритм команды* (Операционка)
   Запустите недельную планёрку 30 мин с одним вопросом: «что мешает достичь фокуса года?».

2. *Конверсия из заявки в договор* (Воронка)
   Один раз руками посчитайте: демо за квартал × договора → базовая конверсия.

3. *Cash на 30 дней* (Деньги)
   Сделайте Sheets с поступлениями и платежами на 30 дней.

— — —
Хотите глубже? *Бизнес-чекап* за 9 000 ₽ — 20 вопросов с цифрами, PDF на 15 страниц + FigJam-карта за 24 часа.
```

**Inline-клавиатура под сообщением 3:**

```
[ 📝 Бизнес-чекап · 9 000 ₽ ]      ← primary
[ 🎬 Plus · 14 000 ₽ — +видео Кати ]
[ 💬 Сначала поговорить ]            ← demo
[ 📊 Получить PDF Score на e-mail ]  ← опц., если consent_marketing
```

### 8.5 Edge-cases

| Случай | Поведение |
|---|---|
| Юзер вышел в середине, вернулся через `/quiz` | Состояние есть в `context.user_data` → спрашиваем «Продолжить с вопроса N или начать сначала?» |
| `/reset` посреди quiz | Очищает FSM, не очищает БД |
| Юзер выбрал «Другое» в P1 (сегмент) | `segment='other'`, бенчмарк не показываем, growth points работают по умолчанию |
| Юзер не выбрал ответ за 24 ч | Через Celery beat task `quiz_remind` — push «У вас остался незавершённый Score, осталось N вопросов: /quiz» (1 раз, потом не дёргаем) |
| Бот падает на середине | `/quiz` восстанавливает state из `context.user_data` (PTB persistence через `PicklePersistence` — НЕ настроено в текущем коде, поэтому **в этом ТЗ не требуем** persistence; восстановление только в пределах одной сессии бота) |

### 8.6 Аналитика

В `events` пишем:

| event | payload |
|---|---|
| `quiz_started` | `{source: 'bot' \| 'site_link' \| 'widget', skip_p1: bool, skip_p2: bool}` |
| `quiz_p1_answered` | `{segment}` |
| `quiz_p2_answered` | `{stage, outlier: bool}` |
| `quiz_question_answered` | `{q_key, score}` — 12 раз |
| `quiz_completed` | `{score, stage, segment, layer_scores, duration_sec}` |
| `quiz_cta_clicked` | `{cta: 'audit' \| 'audit_plus' \| 'demo' \| 'diagnostic_waitlist'}` |
| `quiz_abandoned` | `{last_q_idx, duration_sec}` (через 24 ч молчания) |

---

## 9. ТЗ на сайт

Два сабсёрфейса: **страница `quiz.html`** (полноценная) и **виджет `js/mini-checkup.js`** (всплывающий).

### 9.1 `quiz.html` — полная страница

**Назначение:** lead-magnet, прямой URL `https://elephantdreams.ru/quiz.html`, индексируемый, попадает в hero-блок главной как «⚡ Founder OS Score · 12 вопросов · бесплатно».

#### 9.1.1 Структура

- Header: лого + «Закрыть ✕» (на `/`) — оставляем как сейчас.
- Hero мини-блок (новый):
  - Заголовок: «**Founder OS Score за 4–7 минут**»
  - Подзаголовок: «12 вопросов по 4 слоям бизнеса + сравнение со средним по вашему сегменту»
  - Прогресс-бар 0% → 100%
- Step P1 (segment), Step P2 (size+revenue) — обязательные.
- Steps 1–12 — основные вопросы.
- Step Result — Score + слои + 3 точки роста + CTA.

#### 9.1.2 Visual / UX

- Один вопрос — один screen. Кнопка «Далее» **не нужна** (5 радиокнопок → клик = автопереход через 300 ms на след. шаг с лёгкой анимацией).
- На каждом step внизу — `Назад` (показываем со step 2).
- Прогресс-бар обновляется на каждый ответ.
- На мобильном: кнопки опций — full-width, минимум 56 px высоты, тап-зоны не пересекаются.

#### 9.1.3 Result screen

Один экран, scroll, секции:

1. Большая цифра Score (96–120 px) + цветовая полоса.
2. Лейбл категории.
3. Карточка «Стадия + сегмент + бенчмарк» (как §7.1).
4. Сетка 2×2 — 4 слоя со светофором и progress-bar 0–100.
5. Список из 3 точек роста (карточки).
6. CTA-блок — primary большая кнопка + 2 secondary text-links.
7. Опционально: «Получить PDF на e-mail» (форма) — если согласие на marketing.
8. Микро-копия: «Никому не передаём ваши ответы. Хранение — 152-ФЗ, можно удалить через бота /delete_my_data.»

#### 9.1.4 Логика подключения к боту

- Primary CTA «Бизнес-чекап» → deep-link `https://t.me/edl_os_bot?start=audit_from_score_<session_id>`.
- При клике — **отправляем POST `/api/quiz/submit`** (см. §12.1) с ответами + session_id, чтобы при заходе в бот мы могли найти ответы и **не переспрашивать**.
- session_id хранится в `localStorage` ключ `edl_quiz_session_v2`.
- Если человек прошёл на сайте, потом пришёл в бот **без** клика по кнопке (просто открыл бота) — сопоставляем по telegram_id ↔ session_id (запоминаем deep-link payload).

#### 9.1.5 Технические детали `quiz.html`

- Без фреймворка (vanilla JS) — как сейчас.
- Все данные опросника (P1, P2, 12 вопросов, GROWTH_HINTS, BENCHMARK, STAGE_WEIGHTS) — в одном JSON `js/mini-checkup-canon.json` (новый файл).
- Скрипт `js/quiz-page.js` (новый) — рендерит шаги из JSON, считает Score, рендерит result. Бот и сайт **читают один и тот же JSON** (синхронизация через билд-скрипт: при изменении `core/quiz.py` запускается `scripts/dump_quiz_to_json.py`, который генерирует `js/mini-checkup-canon.json`). См. §15.
- На клиенте: **тот же** алгоритм `total_score / stage_detection / top3_growth_points` — переписанный на JS из Python. Файл `js/mini-checkup-engine.js`.

### 9.2 Виджет `js/mini-checkup.js`

**Назначение:** ненавязчивое предложение пройти Mini-Чекап с любой страницы. Раскрывается через `bot-widget.js` по триггеру (30 сек на странице ИЛИ 30% scroll). Cookie 7 дней — не показывать повторно.

#### 9.2.1 Переписываем существующий

Текущий виджет — диалоговый, 5 вопросов, keyword-based. **Заменяем на multiple-choice 12 вопросов из единого JSON** (тот же canon, что в `quiz.html` и в боте).

#### 9.2.2 UX виджета

- Развёрнутое окно: **480×640** px (десктоп), на мобиле — `100vh - 80px` высоты, 100% ширины.
- Внутри:
  - Header: «Founder OS Score · 14 вопросов · 4–7 мин» + крестик (свернуть на 7 дней)
  - Прогресс-бар
  - Step (P1 / P2 / Q1–Q12 / Result) — один за раз
  - Footer: «Уйти в полную версию» → `quiz.html` с переносом state
- Анимация: fadeUp 200 ms между steps, без бегущей строки (REDUCED_MOTION respected).
- Состояние сохраняется в `localStorage` ключ `edl_widget_quiz_v2`. Если пользователь закрыл — при следующем открытии (с другой сессии): «У вас сохранён прогресс: продолжить или начать заново?».

#### 9.2.3 Result в виджете

Уменьшенная версия result-screen — только:
- Score (60 px)
- Стадия + бенчмарк (1 строка)
- 3 точки роста (с горизонтальным скроллом если не вмещается)
- Один большой CTA «Открыть полный отчёт в Telegram» → deep-link
- Текст под кнопкой: «Полный разбор + 3 действия на эту неделю — в боте»

#### 9.2.4 Тех-детали виджета

- Источник вопросов: `js/mini-checkup-canon.json` (общий с `quiz.html`).
- Engine: `js/mini-checkup-engine.js` (общий).
- На submit — POST в `/api/quiz/submit` + сохранение `widget_session_id` в `localStorage`.
- Если у юзера в `localStorage` есть свежий результат (<24 ч) — при открытии виджета сразу показываем result + предлагаем «Чекап».

### 9.3 Главная (`index.html`) — точки касания виджета

- Hero CTA «⚡ Founder OS Score · 12 вопросов · бесплатно» → `quiz.html`.
- В блоке «Что внутри EDL OS» 02 (по SoT §3.2.6 — он переписывается под agent-парадигму) — компактный mockup результата виджета как **визуальный teaser** (статичный SVG из `checkups/result_mini_widget.svg`).
- Сам виджет — bottom-right на ВСЕХ страницах.

### 9.4 Несовместимости с текущим сайтом

| Текущее | Изменение |
|---|---|
| `quiz.html` 6 вопросов с результатом «спасибо, перейдите в бот» | 14 вопросов с **полноценным result в браузере** |
| `js/mini-checkup.js` — keyword-based 5 вопросов | multiple-choice 12 вопросов + 2 preliminary |
| Hero текст «12 вопросов» в `index.html` | Остаётся (число совпало) — только перепроверить, что нигде нет «5 вопросов» (исторический копирайт из v1.4) |

---

## 10. Связка «сайт ↔ бот»

### 10.1 Сценарий A — прошёл на сайте, кликнул CTA

1. На сайте после Submit: `POST /api/quiz/submit` → возвращает `quiz_session_id` (UUID).
2. Result-screen показывает CTA с deep-link `https://t.me/edl_os_bot?start=audit_from_score_<quiz_session_id>`.
3. Юзер открывает бота → `/start` route парсит payload `audit_from_score_<UUID>` → бот делает `GET /internal/quiz/<UUID>` → получает `{segment, stage, answers, score}` → **не запускает /quiz**, сразу переходит в `/audit` flow и говорит:

   > «Видел, что вы прошли Founder OS Score на сайте. Score = 67, стадия Команда. Рекомендую Чекап Base. Готовы оформить?»

4. Ответы сохраняем в `users` и связанной `QuizSubmission` (см. §11).

### 10.2 Сценарий B — прошёл на сайте, НЕ кликнул CTA, через неделю пришёл в бота

1. На сайте при submit мы **спрашиваем e-mail опционально**: «Получить PDF на e-mail?» (с `consent_marketing`). Если получили e-mail → связать с `User` после первого `/start` если e-mail совпадёт.
2. Иначе — данные остаются только в `quiz_submissions` без user_id.
3. При первом `/start` в боте: сравниваем `localStorage edl_quiz_session_v2` с серверной БД через UTM/cookie не выйдет без идентификатора. **Поэтому в Telegram WebApp** (если бот добавит inline-кнопку «Открыть Score» на сайте) — передаём `initData` с tg_id. Это P2-функционал, в v2.0 не делаем; в v2.0 — просто **deep-link обязателен для связи**.

### 10.3 Сценарий C — прошёл в боте

Стандартный путь: бот хранит всё в `users` + `quiz_submissions`. На сайт ничего не уходит. Если потом юзер захочет «получить PDF-версию» — отправляем PDF в чат бота (опц.).

---

## 11. Изменения БД

### 11.1 Новая таблица `quiz_submissions`

```sql
CREATE TABLE quiz_submissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id BIGINT REFERENCES users(id) NULL,        -- NULL для submissions без авторизации
  source TEXT NOT NULL,                            -- 'bot' | 'site_page' | 'site_widget'
  widget_session_id UUID NULL,                     -- если пришёл из виджета
  segment TEXT NOT NULL,                           -- 'edu' | 'mp' | 'it' | 'prod' | 'serv' | 'saas' | 'other'
  stage TEXT NOT NULL,                             -- 'start' | 'team' | 'structure' | 'maturity'
  stage_confidence TEXT NOT NULL DEFAULT 'high',   -- 'high' | 'low'
  outlier_flag TEXT NULL,                          -- 'small_team' | 'big_team' | NULL
  score INT NOT NULL,                              -- 0..100
  layer_scores JSONB NOT NULL,                     -- {"01": 80, "02": 55, "03": 40, "04": 75}
  answers JSONB NOT NULL,                          -- {q_key: score, ...}
  growth_points JSONB NOT NULL,                    -- [{layer, question_key, action}, x3]
  duration_sec INT NULL,                           -- от start до submit
  consent_marketing_at_submit BOOLEAN DEFAULT FALSE,
  email TEXT NULL,                                 -- опц., для site без auth
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_quiz_submissions_user_id ON quiz_submissions(user_id);
CREATE INDEX ix_quiz_submissions_widget_session_id ON quiz_submissions(widget_session_id);
CREATE INDEX ix_quiz_submissions_created_at ON quiz_submissions(created_at DESC);
```

### 11.2 Новая таблица `benchmark_segment_stage` (P2, не в первом релизе)

```sql
CREATE TABLE benchmark_segment_stage (
  segment TEXT NOT NULL,
  stage TEXT NOT NULL,
  mean_score NUMERIC(5,2) NOT NULL,
  median_score NUMERIC(5,2) NOT NULL,
  sample_size INT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (segment, stage)
);
```

В v2.0 — НЕ создаём, используем хардкод `BENCHMARK`. Создание — отдельный PR после 100+ submissions.

### 11.3 Изменения в `users`

```sql
ALTER TABLE users ADD COLUMN quiz_completed_at TIMESTAMPTZ NULL;
ALTER TABLE users ADD COLUMN quiz_stage TEXT NULL;
-- quiz_score уже есть
```

### 11.4 Alembic-миграция

`alembic/versions/0012_quiz_submissions.py`:
- create `quiz_submissions`
- add columns в `users`

Применяется автоматически через `railway.json:preDeployCommand`.

---

## 12. API контракты (FastAPI)

Добавляем эндпоинты в `src/admin/routes.py` → или **новый файл** `src/api/quiz.py` (рекомендуется, чтобы не мешать с admin).

### 12.1 `POST /api/quiz/submit`

**Auth:** нет (публичный, защищён rate-limit и origin-check).

**Headers:** `Origin: https://elephantdreams.ru` (CORS allowlist).

**Request body:**

```json
{
  "source": "site_page | site_widget",
  "widget_session_id": "uuid | null",
  "segment": "edu",
  "stage_from_p2": "team",          // или 'outlier_small_team'
  "answers": {
    "s1_horizon_3y": 8,
    "s2_year_focus": 5,
    "...": 10
  },
  "duration_sec": 287,
  "email": "string | null",
  "consent_marketing": false
}
```

**Server-side actions:**

1. Валидация: все 12 ключей присутствуют, значения ∈ {0,3,5,8,10}, segment ∈ allowed, stage_from_p2 валидно.
2. Расчёт `score`, `layer_scores`, `growth_points` **через тот же `core/quiz.py`** (DRY).
3. Insert в `quiz_submissions` без user_id.
4. Return:

```json
{
  "quiz_session_id": "uuid",
  "score": 67,
  "category": "Зрелая инфраструктура...",
  "category_color": "yellow",
  "stage": "team",
  "stage_label": "Команда",
  "stage_confidence": "high",
  "segment": "edu",
  "segment_label": "онлайн-школ",
  "layer_scores": {"01": 80, "02": 55, "03": 40, "04": 75},
  "benchmark": {"mean": 54, "delta": 13, "source": "hardcoded"},
  "growth_points": [
    {"layer": "03", "layer_label": "Операционка", "short": "Нет недельного ритма", "action": "Запустите недельную планёрку..."},
    ...
  ],
  "cta": {
    "primary": {"type": "audit", "label": "Бизнес-чекап · 9 000 ₽", "deep_link": "https://t.me/edl_os_bot?start=audit_from_score_<uuid>"},
    "secondary": {"type": "audit_plus", "label": "Plus · 14 000 ₽"}
  }
}
```

### 12.2 `GET /internal/quiz/{quiz_session_id}`

**Auth:** internal — header `X-Internal-Token` (env `INTERNAL_API_TOKEN`).

Используется ботом при deep-link `/start audit_from_score_<UUID>`.

**Response:** полный объект из `quiz_submissions` + `MiniCheckupResult`.

### 12.3 `POST /api/quiz/email-pdf` (P2, не в v2.0)

Заявка на e-mail с PDF Score. Откладываем — Mini-Чекап в v2.0 не генерирует PDF.

### 12.4 Rate-limit

- `POST /api/quiz/submit` — 5 запросов / 1 час с IP (Redis sliding window).
- `GET /internal/quiz/*` — 100 / минута (защита от внутренней ошибки).

### 12.5 CORS

В `src/main.py` — настроить `CORSMiddleware` allowlist `https://elephantdreams.ru` (и `http://localhost:5500` для dev).

---

## 13. Аналитика и события

### 13.1 События на сайте (через `js/edl-track.js`)

| event | properties |
|---|---|
| `mini_quiz_widget_shown` | `{trigger: '30s' \| '30pct_scroll'}` |
| `mini_quiz_widget_dismissed` | `{at_step: 'p1' \| ...}` |
| `mini_quiz_started` | `{source: 'page' \| 'widget'}` |
| `mini_quiz_p1_answered` | `{segment}` |
| `mini_quiz_p2_answered` | `{stage, outlier}` |
| `mini_quiz_question_answered` | `{q_key, score, q_num}` × 12 |
| `mini_quiz_submitted` | `{score, stage, segment, duration_sec}` |
| `mini_quiz_cta_clicked` | `{cta_type, source}` |
| `mini_quiz_page_to_bot_deeplink` | `{quiz_session_id}` |

### 13.2 События в боте

В таблице `events` (см. §8.6) + проброс в `analytics-manifest.json`.

### 13.3 Funnel-метрики (для админ-дашборда `/admin/stats`)

- `quiz_started_count_24h` / `_7d`
- `quiz_completed_count` (= submissions с не-null score)
- `quiz_completion_rate` (completed / started)
- `quiz_to_audit_conversion` (paid audits within 30d / quiz_completed) — целевой 5–10%
- `score_avg_by_segment_stage` (для калибровки бенчмарка)
- `abandon_at_question_distribution` (где люди отваливаются)

---

## 14. Тестирование

### 14.1 Бот (pytest)

| Файл | Тесты |
|---|---|
| `tests/test_quiz_canon.py` | 12 вопросов × 4 слоя; шкала 0/3/5/8/10; уникальные keys; layer ∈ {01,02,03,04} |
| `tests/test_quiz_scoring.py` | `total_score(answers, stage)` — таблицы с ожидаемыми результатами (10 кейсов на стадию × 4 стадии) |
| `tests/test_quiz_stage_detection.py` | все 6 опций P2 + outlier с разными segment'ами |
| `tests/test_quiz_growth_points.py` | для разных answer-векторов растут разные точки роста; не повторяются по слою (если возможно); ровно 3 шт |
| `tests/test_quiz_recommendation.py` | CTA-роутинг (см. §7.3) — таблица Score × Stage → expected CTA |
| `tests/test_quiz_handler_fsm.py` | skip P1/P2 если у user заполнено; `/reset` чистит state; восстановление с N-го вопроса |
| `tests/test_quiz_repo.py` | `mark_quiz_completed` пишет в `quiz_submissions` + обновляет `users.quiz_score`, `quiz_stage`, `quiz_completed_at`, `lead_stage='warm'` |

### 14.2 API

| Файл | Тесты |
|---|---|
| `tests/test_api_quiz_submit.py` | 200 OK happy path; 400 на невалидные answers; CORS; rate-limit; идентичность score между Python и тем же расчётом в JS-engine (запускаем JS через playwright или сравниваем по фикстурам) |
| `tests/test_internal_quiz_get.py` | auth по `X-Internal-Token`; 404 на несуществующий id |

### 14.3 Сайт (E2E, опционально — Playwright)

| Сценарий | Шаги |
|---|---|
| `quiz.html` happy path | Открыть, выбрать P1, P2, 12 ответов, увидеть result, кликнуть CTA → проверить deep-link |
| Виджет триггер | Подождать 30 сек на главной → виджет появился; закрыть → через 7 дней не появляется (фейк-таймер) |
| Виджет → бот | Пройти виджет, кликнуть CTA → проверить, что в payload `quiz_session_id` |
| `quiz.html` pause/resume | Прерваться на Q5, обновить страницу → продолжить с Q5 |

### 14.4 Регрессия копирайта

Тест `test_quiz_copy_no_old_terms.py`:
- В `core/quiz.py` нет ключей `strategy/sales/operations/finance` в user-facing текстах (только в `Layer = 01/02/03/04`).
- Никаких упоминаний «25 000 ₽» (старая цена Диагностики) в текстах рекомендации.
- В `recommendation()` нет «135–260 тыс» (старая цена Спринта).

### 14.5 Score-консистентность Python ↔ JS

Файл-фикстура `tests/fixtures/quiz_scoring_cases.json` — 20 кейсов вида `{answers, stage, expected_score, expected_layers}`.

- `tests/test_quiz_scoring.py` — итерирует фикстуры через Python `total_score()`.
- `tests/scoring_js_check.mjs` (Node) — то же через `js/mini-checkup-engine.js`.
- В CI прогоняется оба, фейлится при расхождении.

---

## 15. Acceptance criteria и roll-out

### 15.1 Acceptance

- [ ] `/quiz` в боте — 2 preliminary + 12 канонических вопросов; result в 3 сообщениях; пишет в `quiz_submissions`; меняет `lead_stage` на `warm`.
- [ ] `quiz.html` — 14 шагов, result в браузере, CTA-deep-link с `quiz_session_id`.
- [ ] Виджет — 14 шагов, result в виджете, CTA в Telegram с переносом.
- [ ] При заходе из сайта в бота с deep-link `audit_from_score_<UUID>` — бот **не переспрашивает** segment/stage и сразу запускает `/audit` flow.
- [ ] Score, layer_scores, growth_points идентичны между Python и JS (фикстура-тест зелёный).
- [ ] Все 24 ячейки бенчмарка `BENCHMARK` корректно подтягиваются; для `other` показываем дефолтную медиану.
- [ ] 184/0 pytest + новые тесты зелёные; LLM regression `--smoke` зелёный.
- [ ] `analytics-manifest.json` обновлён с новыми событиями.

### 15.2 Roll-out (синхронно с SoT §4.1)

| Дата | Шаг |
|---|---|
| **22–24.05** | Pull canon-вопросов из этого ТЗ в `core/quiz.py` + миграция 0012 |
| **24.05** | API `POST /api/quiz/submit` + `GET /internal/quiz/{id}` + CORS |
| **25.05** | Виджет + `quiz.html` переписаны под canon, deploy сайта синхронно с обновлением цен в матрице (по SoT) |
| **26–27.05** | Тесты + регрессия LLM `--critical` |
| **28.05** | Прод-релиз бота (`alembic upgrade head` через preDeployCommand) |
| **29.05–01.06** | Сбор первой воронки (≥50 submissions), проверка `quiz_to_audit_conversion` |
| **15.06** | Если conversion < 5% — пересмотреть копирайт CTA по Score-диапазонам |

### 15.3 Скрипт `scripts/dump_quiz_to_json.py`

Цель: сохранить единый источник правды (`core/quiz.py`) и автоматически генерировать JSON для фронта.

```bash
python scripts/dump_quiz_to_json.py > ../js/mini-checkup-canon.json
```

Поля: questions (12), preliminary (P1, P2), stage_weights, benchmark, growth_hints, category_thresholds.

Запускать вручную перед каждым релизом сайта и в CI (фейлится, если файлы рассинхронизированы).

---

## 16. Что вне скоупа этого ТЗ

- ❌ Чекап и Чекап Plus — отдельное ТЗ `TZ_checkup_plus_v2.md`.
- ❌ Диагностика, Спринт, План Роста.
- ❌ Английская версия Mini-Чекапа (для YC) — после Q3 2026.
- ❌ Динамические бенчмарки из БД (`benchmark_segment_stage`) — после 100+ submissions.
- ❌ PDF Score на e-mail — отложено (см. §12.3).
- ❌ Telegram WebApp вместо deep-link для авторизации submission ↔ user — после v2.0.
- ❌ Mini-Чекап через MCP-сервер в Claude Desktop — отдельный сабпроект, в roadmap §4.1 SoT.
- ❌ Hover-/calculator-интерактивности на сайте — P2 (после 1-го Sprint клиента, июль).
- ❌ Cross-customer benchmark по respondent'ам (sample_size growth, weighted mean) — P3.
- ❌ Persistence FSM бота через `PicklePersistence` — не требуется в v2.0.

---

## Приложение A · Маппинг старых ключей → новых

| Старый key (`core/quiz.py:24-172`) | Новый key | Изменение |
|---|---|---|
| `strategy_direction` | `s1_horizon_3y` | формулировка та же, обновлён номер |
| `strategy_focus` | `s2_year_focus` | без изменений по сути |
| `strategy_not_doing` | `s3_not_doing` | без изменений |
| `sales_pipeline` | `f1_pipeline_home` | без изменений |
| `sales_conversion` | `f2_conv_demo_deal` | без изменений |
| `sales_cycle` | `f3_deal_cycle` | без изменений |
| `ops_load` | `o1_team_load` | без изменений |
| `ops_margin` | — | **удалён** (переезжает в Чекап) |
| `ops_bottleneck` | `o2_bottleneck` | без изменений |
| — | `o3_rhythm` | **новый** (ритм команды) |
| `finance_cash` | `m2_cash_30d` | без изменений |
| `finance_margin` | `m1_company_margin` | без изменений |
| `finance_vat` | `m3_vat_2026` | без изменений |

При миграции — старые ответы из `events` (если кто-то проходил `/quiz` до релиза) **не перерассчитываем** в новой формуле; помечаем как `quiz_score_v1`. Новые проходы — `quiz_score_v2`.

---

## Приложение B · Чек-лист «не пропустить»

- [ ] Bot Token не светится в логах (помнить про `httpx` WARNING — уже стоит).
- [ ] PD: e-mail на сайте — только при `consent_marketing=true`; сохраняем в `pd_access_log` как `read` от actor='public_api'.
- [ ] `quiz_submissions.answers` — JSONB, sanitized (для P1/P2 — нет ПД; для 12 вопросов — числовые scores; PD не возникает).
- [ ] CORS allowlist строгий (`https://elephantdreams.ru` + `https://www.elephantdreams.ru`).
- [ ] `INTERNAL_API_TOKEN` — новая env-переменная, обязательна. Bot читает из `core/config.py`.
- [ ] При `/delete_my_data` — пометить связанные `quiz_submissions.user_id = NULL` (анонимизация, не удаление — нужно для бенчмарков).
- [ ] Бенчмарк-делта подкрашена цветом: ≥+5 зелёный, −5..+5 серый, ≤−5 красный (с уточнением «отстаёте от среднего, но это нормально на переходе»).
- [ ] Никаких упоминаний агентов / consent-модели / MCP в Mini-Чекапе — это для Чекапа/Диагностики/Спринта (Mini = wedge, не сложно).

---

*EDL OS · ТЗ Mini-Чекап v2.0 · 21.05.2026*
