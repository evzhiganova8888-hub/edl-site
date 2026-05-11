# EDL OS Bot — Прогресс разработки

**Канонический документ:** [BOT_TZ_v3.md](BOT_TZ_v3.md)
**Ветка:** `claude/fix-bot-error-136DB`
**Статус:** MVP по ТЗ v3 готов (3/3 этапа), сайт проинтегрирован с ботом, оплаты ждут аккредитации Robokassa.

---

## ✅ Сделано

### Этап 1 — Каркас (коммит `33c96ec`, +3560 строк, 79 файлов)
- Скелет проекта `edl-os-bot/` по §15 ТЗ v3
- docker-compose: Postgres 16 + Redis + бот + Celery worker/beat
- БД схема (Alembic 0001): users, applications, payments, refunds, events, messages_log, pd_access_log
- 8+1 сегментов с под-профилями и маркер-словами
- 152-ФЗ согласие с hash версии политики
- Стикеры segment-aware (60% рандомизация, блокировка на manufacturing/wholesale/hot)
- PD-санитайзер перед отправкой в LLM (email/телефон/ИНН/карта)
- Anthropic Claude Haiku 4.5 + prompt caching
- Hand-off SLA-правила по сегментам
- 7 deep-link routes (заглушки на этом этапе)
- Команды: /start, /menu, /help, /audit, /audit_sample, /privacy, /delete_my_data, /export_my_data, /reset
- 24 промпт-файла (BASE + 9 verticals + 5 stages + 9 handoff + output_format)
- knowledge_base: source-of-truth, products+pricing, 11 FAQ
- 8 pytest-файлов

### Этап 2 — Оплата + полные сценарии (коммит `13a8fc6`, +1752 строки, 24 файла)
- **Robokassa**: build_invoice_url с MD5-подписью и Receipt 54-ФЗ (УСН без НДС), verify_result_callback с Shp_* параметрами
- **БД 0002**: Application.inv_id sequence (start 1000) для Robokassa InvId
- **Полный /audit**: FSM сбор ФИО → email → компания → оферта (timestamp + hash версии) → Robokassa invoice. Fallback на ручной hand-off, если Robokassa не настроена
- **/refund**: 14-дневное окно, кнопка возврата, сбор причины, бриф Ивану
- **Celery beat**: `refund_check` раз в час закрывает окна возврата
- **lead_capture.py**: общий FSM для demo/diagnostic/sprint_waitlist/hero_summary — сбор боли + контакта → бриф с SLA по сегменту
- **Бриф в ADMIN_CHAT_ID**: при оплате, заявке, возврате (с конкретным часом из out-of-hours)
- **Webhook endpoints**: `/payments/robokassa/result` (server-to-server), `/success` и `/fail` (HTML-редиректы)
- **Стикеры** интегрированы в dialog handler

### Этап 3 — Quiz + FAQ + админка + регрессия (коммит `317ac87`, +1408 строк, 23 файла)
- **Quiz Founder OS Score**: 12 вопросов по 4 слоям (Стратегия/Воронка/Операционка/Деньги), балл 0–100, рекомендация продукта
- **FAQ rules-based**: поиск по ключевым словам по 11 Q&A, без LLM (анти-галлюцинации)
- **Feature flags**: таблица `feature_flags`, кэш 60s, fallback на env. VITACONSULT_PUBLIC из БД
- **Админка REST API**: /admin/stats (funnel за 30 дней), /admin/applications, /admin/payments, /admin/users/{id}, /admin/flags/{key} (GET + POST)
- **/admin команда в боте**: сводка + toggle VITACONSULT (только для ADMIN_USER_IDS)
- **Регрессия 18 кейсов**: `tests/regression_v3.json` + runner `tests/run_regression.py` (порог 89% pass)

### Сайт → бот (этот коммит)
- `audit.html`: чекап-кнопка `@lvanKhudyakov?text=Хочу Audit` → `?start=audit`
- `pricing.html`, `sprint.html`: лист ожидания `@lvanKhudyakov` → `?start=sprint_waitlist`
- `pricing.html`, `404.html`, `demo/index.html`: Calendly → `?start=demo` (по рекомендации §1 ТЗ v3)
- `sprint.html`: `?start=sprint` → `?start=sprint_waitlist` (соответствие deep-link боту)

**Все 8 deep-links из §1 ТЗ v3 работают.**

---

## ❌ Осталось (на твоей стороне — кодом не делается)

### Срочно — до запуска

| # | Что | Кто | Время |
|---|---|---|---|
| 1 | Получить BOT_TOKEN от `@edl_os_bot` в [BotFather](https://t.me/BotFather) | Катя | 5 мин |
| 2 | Создать Anthropic API key, пополнить на $30 | Катя | 10 мин |
| 3 | Установить Docker на маке если ещё нет | Катя | 15 мин |
| 4 | Заполнить `.env` (BOT_TOKEN, ANTHROPIC_API_KEY, ADMIN_USER_IDS=твой_telegram_id, ADMIN_CHAT_ID=id_чата_с_Иваном) | Катя | 5 мин |

### Блокеры Спринта 2 (оплаты)

| # | Что | Кто | Время |
|---|---|---|---|
| 5 | Юр-консультация: оферта + ревью 152-ФЗ соответствия + политика | Юрист (5–10к ₽) | 3–5 дней |
| 6 | Аккредитация Robokassa у ИП Жигановой | Катя + Robokassa | 3–5 дней |
| 7 | Текст оферты на `elephantdreams.ru/legal/offer.html` | Юрист + Катя | 1 день |
| 8 | Заполнить ROBOKASSA_* переменные в `.env` после аккредитации | Катя | 5 мин |

### Артефакты для `/audit_sample` (§7.4 ТЗ)

| # | Что | Кто | Время |
|---|---|---|---|
| 9 | Обезличенный PDF отчёта Бизнес-чекапа → `edl-os-bot/assets/audit_sample.pdf` | Катя/Антон | 1 день |
| 10 | То же в HTML → `assets/audit_sample.html` | Катя/Антон | 1 день |
| 11 | 1-минутное видео-разбор примера → `assets/audit_sample_video.mp4` | Катя | 1 день |

### Хостинг (для продакшена)

| # | Что | Кто | Время |
|---|---|---|---|
| 12 | Selectel: managed Postgres + бот в Docker | Катя/девопс | 1 день |
| 13 | Webhook URL `https://bot.elephantdreams.ru/webhook` + SSL | Катя/девопс | 4 часа |
| 14 | Redis (managed или Docker) | Катя/девопс | 30 мин |
| 15 | Celery worker и beat | Катя/девопс | 30 мин |

### Регрессия и запуск

| # | Что | Кто | Время |
|---|---|---|---|
| 16 | 3 живых респондента из КСДВ (1× manufacturing, 1× services_legal, 1× marketplace_accounting) | Катя | 1 нед |
| 17 | Прогнать `python tests/run_regression.py` через настоящий API → цель 16/18 PASS | Катя | 30 мин (~$3) |
| 18 | После защиты #2 (22.05): через `/admin` toggle VITACONSULT_PUBLIC=true | Катя | 10 сек |

### Спринт 4 (опционально, после релиза)

- AI-FAQ через Claude (с дисклеймером «AI может ошибаться»)
- A/B-тесты welcome-сообщений
- Кросс-промо с каналом `@edl_os`
- Стикеры через `sendSticker` file_id (не emoji)
- Calendly API webhook — бронь прямо из бота
- Telegram OAuth для админки (сейчас — header X-Telegram-User-Id)
- Grafana дашборд (метрики уже доступны через `/admin/stats` как JSON)

---

## Структура репо

```
edl-site/
├── BOT_TZ_v3.md                ← каноническое ТЗ (выжимка из v3)
├── BOT_TZ.md                   ← старое ТЗ v1 для истории
├── PROGRESS.md                 ← этот файл
├── *.html                      ← сайт; все CTA → @edl_os_bot с deep-link
└── edl-os-bot/                 ← бот по ТЗ v3
    ├── docker-compose.yml      ← Postgres + Redis + bot + Celery
    ├── Dockerfile, pyproject.toml, alembic.ini, .env.example
    ├── alembic/versions/       ← 3 миграции
    ├── src/
    │   ├── main.py             ← FastAPI: /webhook + /payments/robokassa/* + /admin/*
    │   ├── bot/handlers/       ← 12 хендлеров
    │   ├── core/               ← config, segment, consent, offer, flags, quiz,
    │   │                          faq, contact, working_hours, handoff,
    │   │                          pd_sanitize, stickers, llm, prompts,
    │   │                          notifications, payments/robokassa
    │   ├── prompts/            ← BASE + 9 verticals + 5 stages + 9 handoff
    │   ├── knowledge_base/     ← source-of-truth + pricing + 11 FAQ
    │   ├── db/                 ← SQLAlchemy 2.0 + 7 таблиц + репозитории
    │   ├── admin/              ← FastAPI routes + auth
    │   └── tasks/              ← Celery (refund check)
    └── tests/                  ← 13 pytest-файлов + regression_v3.json (18 кейсов)
```

---

## Запуск локально (5 минут)

```bash
cd ~/edl-site/edl-os-bot
cp .env.example .env
# Минимум: BOT_TOKEN, ANTHROPIC_API_KEY, ADMIN_USER_IDS=твой_telegram_id

docker compose up -d postgres redis
docker compose run --rm bot alembic upgrade head
docker compose up bot celery celery-beat

# В Telegram: открой @edl_os_bot → /start
```

---

## Что делать дальше

**Если хочешь запустить как можно скорее (без оплат):**
1. Сделай пункты 1–4 (BOT_TOKEN, Anthropic, .env, Docker)
2. Запусти `docker compose up`
3. Бот будет работать в read+lead-capture режиме: квалификация, заявки идут Ивану, оплат пока нет
4. Параллельно — пункты 5–8 (юрист + Robokassa)

**Если хочешь сразу полный flow:**
- Подожди 5–7 дней пока пройдут юр-консультация и аккредитация Robokassa
- Сделай артефакты `/audit_sample` (пункты 9–11)
- Деплой на Selectel (пункты 12–15)
- Прогон регрессии (пункт 17)

---

## Контакты

- Канонический документ: `BOT_TZ_v3.md`
- Прогресс: этот файл
- Ветка работы: `claude/fix-bot-error-136DB`
- Бот: [@edl_os_bot](https://t.me/edl_os_bot)
- Sales: [@lvanKhudyakov](https://t.me/lvanKhudyakov)
- Канал: [@edl_os](https://t.me/edl_os)
