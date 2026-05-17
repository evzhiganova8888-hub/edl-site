# EDL OS Bot — source of truth

> Project memory для Claude Code. Описывает что реально работает в коде и в проде на 2026-05-17.
> При расхождениях между этим документом и старыми ТЗ (`/BOT_TZ.md`, `/BOT_TZ_v3.md`) — **доверяй коду и этому файлу**.
> Старые ТЗ оставлены для исторического контекста, но они описывают цели, а не реализацию.

---

## 1. Что это

Telegram-бот **@edl_os_bot** для продажи и доставки «Бизнес-чекапа EDL OS» (9 000 ₽ Base / 14 000 ₽ Plus) и захвата лидов на другие тарифы (Спринт 25 000 ₽ — лист ожидания).

- **Прод**: https://elephantdreams.ru + Railway (проект `efficient-appreciation`, сервис `edl-site`).
- **Bot**: https://t.me/edl_os_bot
- **Репо**: https://github.com/evzhiganova8888-hub/edl-site (основной код бота — в подкаталоге `edl-os-bot/`).

## 2. Tech stack

| Слой | Стек |
|------|------|
| Bot framework | python-telegram-bot 21 (PTB) |
| HTTP / webhook | FastAPI + uvicorn |
| ORM | SQLAlchemy 2 async (asyncpg для рантайма, psycopg3 для миграций) |
| Миграции | Alembic |
| Cache / rate-limit | Redis (`redis.asyncio`) |
| LLM | Anthropic Claude Haiku 4.5 (через `proxyapi.ru` для рублевой оплаты) |
| PDF | WeasyPrint |
| Background jobs | Celery (worker + beat) |
| Платежи | Stub (manual через `/mark_paid`) — yookassa-клиент в коде, выключен |
| Hosting | Railway (Dockerfile builder + Postgres + Redis addons) |
| Python | 3.12-slim |

## 3. Структура проекта

```
edl-os-bot/
├── src/
│   ├── main.py                    # FastAPI app + PTB lifespan + endpoints
│   ├── bot/
│   │   ├── handlers/              # 22 commands + 19 callback handlers
│   │   │   ├── __init__.py        # registry (CommandHandler / CallbackQueryHandler / MessageHandler)
│   │   │   ├── start.py           # /start /menu /help /reset + deep-link routing
│   │   │   ├── audit.py           # /audit /audit_sample + FSM покупка Чекапа
│   │   │   ├── checkup.py         # /checkup — FSM 20 вопросов
│   │   │   ├── admin.py           # /admin /mark_paid /applications /emails_dump /beta_summary
│   │   │   ├── admin_login.py     # /admin_login /admin_logout (HMAC + Redis rate-limit)
│   │   │   ├── consent.py         # PD consent flow (152-ФЗ)
│   │   │   ├── privacy.py         # /privacy /delete_my_data /export_my_data
│   │   │   ├── faq.py             # /faq + 11 rules-based тем
│   │   │   ├── quiz.py            # /quiz — 12 вопросов Founder OS Score
│   │   │   ├── refund.py          # /refund — 14-дневное окно
│   │   │   ├── lead_capture.py    # demo / diagnostic / sprint_waitlist / hero_summary flows
│   │   │   ├── feedback.py        # /feedback + waitlist callbacks
│   │   │   ├── bugs.py            # /bugs (admin)
│   │   │   ├── bug_report.py      # inline 🤔 «Неточно» под LLM ответами
│   │   │   └── dialog.py          # FSM-роутер для свободного текста → LLM
│   │   ├── keyboards.py           # все InlineKeyboardMarkup
│   │   └── texts.py               # все user-facing строки на русском
│   ├── core/
│   │   ├── config.py              # Settings (pydantic-settings) — single source of truth для env
│   │   ├── llm.py                 # Anthropic клиент + retry + prompt caching
│   │   ├── prompts.py             # system prompts по сегментам
│   │   ├── pd_sanitize.py         # фильтр ПД и секретов перед LLM (152-ФЗ scope)
│   │   ├── scope_guard.py         # whitelist+blacklist детерминированный off-topic фильтр
│   │   ├── input_validation.py    # длина ≤4000, NUL/control/bidi-override фильтр
│   │   ├── rate_limit.py          # Redis sliding window (message / payment / LLM tokens)
│   │   ├── memory.py              # сессионный recap (build_user_recap → recap_to_prompt_snippet)
│   │   ├── segment.py             # detect_from_deep_link / detect_from_text / sub_profile
│   │   ├── stickers.py            # should_send_sticker + pick_emoji
│   │   ├── handoff.py             # SLA per segment → manufacturing/services/marketplace/other
│   │   ├── notifications.py       # build_*_brief + send_to_admin_chat
│   │   ├── working_hours.py       # in_hours / next_window (МСК + RF_HOLIDAYS до 2027)
│   │   ├── contact.py             # normalize_full_name / normalize_email / normalize_company
│   │   ├── consent.py             # has_consent / record + version
│   │   ├── offer.py               # accept_offer + offer_summary (хеш стабилен)
│   │   ├── flags.py               # FLAG_VITACONSULT_PUBLIC (NDA до 22.05.2026)
│   │   ├── payment_marking.py     # mark_application_paid (idempotent)
│   │   ├── faq.py                 # 11 тем
│   │   ├── quiz.py                # 12 вопросов + scoring
│   │   ├── checkup_questions.py   # 20 вопросов × 4 слоя (strategy/sales/operations/finance)
│   │   ├── checkup_report.py      # HTML→PDF через WeasyPrint
│   │   ├── feedback.py            # категории + severity
│   │   └── payments/
│   │       ├── stub.py            # текущий режим
│   │       └── yookassa.py        # клиент, dormant (PAYMENT_MODE=yookassa)
│   ├── db/
│   │   ├── models.py              # 12 SQLAlchemy моделей
│   │   ├── repos.py               # async repository helpers
│   │   └── session.py             # async_session_factory + engine
│   ├── admin/
│   │   ├── auth.py                # is_admin / is_admin_active / require_admin
│   │   └── routes.py              # FastAPI admin API endpoints (см. §7)
│   └── tasks/
│       ├── celery_app.py
│       ├── generate_checkup_pdf.py
│       ├── refund_check.py
│       └── weekly_voc.py
├── alembic/
│   ├── env.py                     # читает DATABASE_URL → форсит postgresql+psycopg://
│   └── versions/                  # 0001 → 0007 (см. §6)
├── tests/                         # 36 файлов, 165 passing
├── docs/
│   ├── runbook.md                 # типовые проблемы прода
│   ├── release_checklist.md       # gate-лист
│   ├── threat_model.md            # T1–T11
│   ├── post_beta_quality_playbook.md
│   ├── voc_ritual.md
│   ├── TZ_v3_1_hardening_patch.md
│   └── qa_audit_2026-05-17/       # отчёты QA-аудита (bug_log, gap_log, test_report, improvement_plan, RAILWAY_WEBHOOK_SETUP, MIGRATION_FIX, SESSION_REPORT)
├── assets/
│   └── audit_sample.html          # пример отчёта Чекапа
├── alembic.ini
├── pyproject.toml
├── Dockerfile                     # python:3.12-slim + Pango/HarfBuzz/Liberation+DejaVu шрифты
├── Procfile                       # web + release (release игнорится при Dockerfile builder в Railway)
├── railway.json                   # builder=DOCKERFILE, preDeployCommand=alembic upgrade head
├── docker-compose.yml             # postgres + redis + bot + celery + celery-beat
└── .env.example                   # все env vars (см. §5)
```

## 4. Точки входа (FastAPI + PTB)

`src/main.py`:

- **Lifespan startup**: `build_application()` → `_ptb_app.initialize()` → `_ptb_app.start()`. Если `WEBHOOK_BASE_URL` задан → `set_webhook(url, secret_token, drop_pending_updates=True)`. Иначе → `asyncio.create_task(_run_polling(...))` (только dev).
- **Lifespan shutdown**: `_ptb_app.stop()` + `_ptb_app.shutdown()`. **Не вызывает `delete_webhook`** (это намеренно — Railway rolling deploy → race).
- HTTP middleware `_log_requests` логирует каждый HTTP-запрос (`HTTP POST /webhook -> 200`).
- httpx и httpcore loggers выставлены в WARNING (BOT_TOKEN не светится в логах).

**FastAPI endpoints:**

| Method | Path | Handler | Назначение |
|--------|------|---------|-----------|
| GET | `/health` | `main.health` | Liveness — `{"status":"ok", "use_webhook":...}` |
| POST | `/webhook` | `main.telegram_webhook` | Telegram updates. Проверяет `X-Telegram-Bot-Api-Secret-Token`. Кладёт update в `_ptb_app.update_queue` и сразу возвращает 200 OK (non-blocking) |
| GET | `/admin/stats` | `admin.routes.stats` | 30-day сводка |
| GET | `/admin/applications` | `admin.routes.applications` | Список заявок (фильтры status/limit) |
| GET | `/admin/payments` | `admin.routes.payments` | Платежи |
| GET | `/admin/users/{telegram_id}` | `admin.routes.user_card` | Карточка юзера |
| GET | `/admin/flags/{key}` | `admin.routes.get_flag` | Feature flag |
| POST | `/admin/flags/{key}` | `admin.routes.set_flag` | Toggle feature flag |
| GET | `/admin/bot_errors` | `admin.routes.bot_errors` | Bug reports |
| POST | `/admin/applications/{id}/mark-paid` | `admin.routes.mark_paid` | Ручная отметка оплаты |
| POST | `/admin/bot_errors/{id}/review` | `admin.routes.review_error` | Закрыть bug-report |

Admin API защищён `X-Telegram-User-Id` header → проверка через `require_admin()` против `ADMIN_USER_IDS` env.

## 5. Конфигурация (env vars)

Source of truth: `src/core/config.py:Settings` (pydantic-settings). Реальные значения — в Railway → Variables. `.env.example` синхронизирован.

| Переменная | Назначение | Без чего не работает |
|-----------|------------|---------------------|
| `BOT_TOKEN` | Telegram bot token | Бот вообще |
| `BOT_USERNAME` | Для deep-link URL'ов | Кнопки с deep-link |
| `ADMIN_USER_IDS` | tg_id'ы через запятую, имеют права всех команд без `/admin_login` | Admin commands |
| `ADMIN_CHAT_ID` | Чат для брифов и сервис-уведомлений | Брифы Ивану |
| `DATABASE_URL` | Postgres. На Railway = `${{Postgres.DATABASE_URL}}` (internal `postgres.railway.internal`) | Всё |
| `REDIS_URL` | Redis. На Railway = `${{Redis.REDIS_URL}}` | Rate-limit, /admin_login |
| `ANTHROPIC_API_KEY` | Claude API | LLM |
| `ANTHROPIC_BASE_URL` | `https://api.proxyapi.ru/anthropic` (рублёвая оплата) | LLM без зарубежной карты |
| `ANTHROPIC_MODEL` | По умолчанию `claude-haiku-4-5-20251001` | — |
| `ANTHROPIC_MAX_TOKENS` | По умолчанию 600 | — |
| `PAYMENT_MODE` | `stub` / `manual` / `yookassa` | Покупка |
| `YOOKASSA_SHOP_ID` / `YOOKASSA_SECRET_KEY` | YooKassa creds | Только если PAYMENT_MODE=yookassa |
| `BOT_ADMIN_ACCESS_KEY` | Для `/admin_login`. Если пусто — фича выключена | `/admin_login` |
| `ADMIN_SESSION_HOURS` | По умолчанию 8 | TTL admin-сессий |
| `WEBHOOK_BASE_URL` | Если задан — webhook mode | Прод (без него — polling, что плохо на Railway) |
| `WEBHOOK_SECRET_TOKEN` | Должен совпадать у Telegram и handler | Защита /webhook |
| `PRIVACY_POLICY_VERSION` | Дата версии политики (`2026-05-11`) | Версирование consent |
| `OFFER_URL` / `OFFER_CHECKUP_URL` / `PRIVACY_POLICY_URL` | Ссылки на лендинг | Тексты |
| `VITACONSULT_PUBLIC` | false до 22.05.2026 (NDA), потом true | Упоминание клиента в публичных текстах |
| `WORKING_HOURS_START/END` | 10/19 МСК | SLA на эскалацию |
| `TIMEZONE` | `Europe/Moscow` | — |
| `LOG_LEVEL` | По умолчанию `INFO` | — |
| `ENVIRONMENT` | `production` / `development` | Polling-warning, hot-reload |

## 6. БД-схема

### 6.1 Модели (`src/db/models.py`)

| Модель | Таблица | Назначение |
|--------|---------|-----------|
| `User` | users | telegram_id (unique), email, first/last name, company, segment, sub_profile, stage, consent_pd_*, wants_followup_report, quiz_score |
| `Application` | applications | UUID id + inv_id (sequence), type (audit/diagnostic/sprint_waitlist/...), status (new/qualified/awaiting_manual_payment/paid), checkup_started_at, checkup_completed_at, checkup_pdf_url, refund_eligible_until |
| `Payment` | payments | application_id, amount_kopecks, provider (`manual_admin`/`yookassa`), provider_invoice_id, status (pending/succeeded/refunded) |
| `Refund` | refunds | application_id, reason, status (requested/approved/refused/refunded) |
| `Event` | events | event (str), user_id, payload (jsonb), occurred_at — audit trail / VoC |
| `MessageLog` | messages_log | direction (inbound/outbound), text, llm_tokens, sticker_sent, vat_topic_mentioned |
| `PDAccessLog` | pd_access_log | actor, action (read/update/delete/export), fields[] — 152-ФЗ audit |
| `FeatureFlag` | feature_flags | key, enabled, actor, updated_at |
| `BotError` | bot_errors | message_log_id, user_id, severity, comment — inline «🤔 Неточно» |
| `Feedback` | feedback | step, category, severity, comment, reviewed_at — `/feedback` flow |
| `AdminSession` | admin_sessions | telegram_id, granted_by, expires_at, revoked_at — `/admin_login` |
| `CheckupAnswer` | checkup_answers | application_id + question_key (uniq), layer, text, word_count, quality_passed |

### 6.2 Миграции (`alembic/versions/`)

| Файл | Что добавляет |
|------|---------------|
| `0001_initial.py` | users, applications, payments, refunds, events, messages_log, pd_access_log |
| `0002_application_inv_id.py` | sequence для `inv_id` (стабильный номер счёта) |
| `0003_feature_flags.py` | feature_flags |
| `0004_bot_errors.py` | bot_errors + индекс по (user_id, reported_at) |
| `0005_feedback.py` | feedback + users.wants_followup_report |
| `0006_admin_sessions.py` | admin_sessions + applications.checkup_* колонки |
| `0007_checkup_answers.py` | checkup_answers (uniq на (application_id, question_key)) |

**Текущий head**: `0007_checkup_answers`. Применяется автоматически через `railway.json:preDeployCommand`.

### 6.3 alembic/env.py

Читает `SYNC_DATABASE_URL` или `DATABASE_URL` из env. Принудительно переписывает `postgresql://` и `postgresql+asyncpg://` → `postgresql+psycopg://` (Dockerfile ставит только psycopg3).

## 7. Команды Telegram-бота

Registry: `src/bot/handlers/__init__.py:register()`.

### 7.1 Команды (22)

| Команда | Handler | Назначение |
|---------|---------|-----------|
| `/start [payload]` | `start.start_command` | Меню + 7 deep-link routes (`demo`, `audit`, `audit_sample`, `diagnostic`, `sprint_waitlist`, `hero_summary`, `quiz`) |
| `/menu` | `start.menu_command` | Повторное меню |
| `/help` | `start.help_command` | Список команд |
| `/reset` | `start.reset_command` | Очищает `context.user_data` (FSM) |
| `/audit` | `audit.audit_command` | Лендинг Чекапа |
| `/audit_sample` | `audit.audit_sample_command` | PDF/HTML пример отчёта |
| `/checkup` | `checkup.checkup_command` | FSM 20 вопросов (требует paid Application) |
| `/refund` | `refund.refund_command` | Возврат в течение 14 дней с `refund_eligible_until` |
| `/faq` | `faq.faq_command` | 11 тем (rules-based, без LLM) |
| `/quiz` | `quiz.quiz_command` | 12 вопросов Founder OS Score |
| `/privacy` | `privacy.privacy_command` | Список согласий |
| `/delete_my_data` | `privacy.delete_my_data_command` | Soft-delete + `pd_access_log` |
| `/export_my_data` | `privacy.export_my_data_command` | JSON-выгрузка |
| `/admin` | `admin.admin_command` | Админ-панель (требует ADMIN_USER_IDS) |
| `/admin_login <KEY>` | `admin_login.admin_login_command` | HMAC-сессия 8ч (rate-limit 3/10мин → 1ч блок) |
| `/admin_logout` | `admin_login.admin_logout_command` | Отзыв всех активных AdminSession |
| `/mark_paid <UUID> <amount> [ref]` | `admin.mark_paid_command` | Помечает заявку paid + уведомляет юзера + idempotent |
| `/applications [pending\|paid\|all] [limit]` | `admin.applications_command` | Список заявок |
| `/emails_dump` | `admin.emails_dump_command` | CSV всех email (paid) |
| `/beta_summary` | `admin.beta_summary_command` | Сводка отзывов и багов |
| `/bugs` | `bugs.bugs_command` | Пагинация unresolved bug-report (admin) |
| `/feedback` | `feedback.feedback_command` | (admin) обзор feedback |

### 7.2 Callback patterns (19)

| Pattern | Handler |
|---------|---------|
| `consent:*` | `consent.handle_consent` |
| `menu:*` | `start.handle_menu_button` |
| `segment:*` | `start.handle_segment_button` |
| `audit:start_purchase[:base\|plus]` | `audit.start_purchase` |
| `audit:cancel_collection` | `audit.cancel_collection` |
| `audit:notify_waiting` | `audit.notify_waiting` |
| `offer:*` | `audit.handle_offer` |
| `refund:request:*` | `refund.handle_refund_callback` |
| `privacy:*` | `privacy.handle_privacy_action` |
| `quiz:ans:*` | `quiz.handle_answer` |
| `quiz:cancel` | `quiz.handle_cancel` |
| `faq:show:*` | `faq.handle_show` |
| `admin:*` | `admin.handle_admin_callback` |
| `admin_login:hint` | `admin_login.admin_login_hint` |
| `checkup:*` | `checkup.handle_checkup_callback` |
| `bugreport:*` | `bug_report.handle_callback` |
| `bug:*` | `bugs.handle_bug_callback` |
| `feedback:*` | `feedback.handle_callback` |
| `waitlist:*` | `feedback.handle_waitlist_callback` |

### 7.3 Free-text (FSM-router)

`MessageHandler(filters.TEXT & ~filters.COMMAND, dialog.handle_text)` — порядок проверки:

1. Rate limit (`rate_limit.check_message` — Redis sliding window)
2. Input validation (длина ≤4000, NUL/control/bidi)
3. FSM-шаги (приоритет важен):
   - `admin.handle_text_step` (toggle reason для VITACONSULT)
   - `bug_report.handle_text_step` (короткий)
   - `checkup.handle_text_step` (ответы на 20 вопросов)
   - `audit.handle_text_step` (ФИО → email → company)
   - `refund.handle_text_step` (причина)
   - `lead_capture.handle_text_step` (demo/diagnostic/sprint_waitlist/hero_summary)
   - `faq.handle_text_step`
   - `feedback.handle_text_step` (в самом низу, чтобы не съесть FSM покупки)
4. `scope_guard.is_off_topic()` → canned-ответ без LLM
5. LLM dialog (Claude Haiku) + sticker + bug-report кнопка под ответом

## 8. FSM-сценарии

| Сценарий | FSM-keys в `context.user_data` | States |
|----------|--------------------------------|--------|
| Audit purchase | `audit_flow_state`, `audit_application_id`, `audit_plan` | `await_full_name` → `await_email` → `await_company` → offer |
| Checkup | `checkup_state`, `checkup_app_id`, `checkup_q_idx` | `await_start` → `await_ready` → `await_answer` × 20 |
| Refund | `refund_application_id`, FSM в `refund.py` | reason → confirm |
| Lead capture | `lead_capture_flow`, `lead_capture_state` | step-зависимый |
| Bug report | `bug_report_pending_message_id` | comment / skip |
| Feedback | `feedback_flow_step`, `feedback_category` | category → severity → comment |
| Admin toggle | `admin_pending_toggle` | reason (≥3 символов) |

`/reset` → `context.user_data.clear()`. БД не трогается.

## 9. LLM подсистема

`src/core/llm.py:reply()`:

1. `sanitize(user_text)` — `pd_sanitize` маскирует email, phone, INN, card, TG username, name pattern, **secrets** (telegram_token, anthropic_key, openai_key, github_pat).
2. `build_system_prompt(segment, stage, vitaconsult_public, recap_snippet)` — кэшируется через Anthropic prompt caching.
3. `AsyncAnthropic.messages.create(...)` — `claude-haiku-4-5`, max_tokens=600, через `proxyapi.ru` если задан `ANTHROPIC_BASE_URL`.
4. Retry 3 раза с exponential backoff (`tenacity`).
5. Логирует tokens + cache hit rate.

**Регрессия** (платная, `python tests/run_regression_v3_1.py`):
- `--smoke` (10 кейсов) — бесплатно
- `--critical` (30: 5×sycophancy + 5×adversarial + ...) — ~50₽
- full (84 кейса) — ~150-300₽

## 10. Глобальный error handler

`src/bot/handlers/__init__.py:_global_error_handler` ловит любой неперехваченный exception:

1. Логирует traceback.
2. Отвечает юзеру: «Что-то пошло не так на нашей стороне. Я уже сообщил команде. Если срочно — напишите Ивану: @{sales_username}. Чтобы вернуться в меню: /menu»
3. Пишет в `events` строку `event='unhandled_exception'`, `payload={type, error, tb_tail[-1500:]}`.

Защита от каскада: try-except на reply (юзер мог заблокировать бота) + try-except на DB-логирование.

## 11. Security

| ID | Угроза | Контроль |
|----|--------|---------|
| T1 | PD-leak в LLM | `pd_sanitize.sanitize()` в `llm.reply` |
| T2 | Off-topic LLM | `scope_guard.is_off_topic()` whitelist+blacklist+min_words |
| T3 | Prompt injection | system prompt anti-injection + adversarial regression |
| T4 | Brute-force `/admin_login` | Redis rate-limit (3/10мин → 1ч блок) |
| T5 | Подмена админа через ENV | `is_admin()` + `is_admin_active()` |
| T6 | Кража AdminSession | `expires_at` + `revoked_at` + `hmac.compare_digest` |
| T7 | SQL injection | SQLAlchemy ORM (нет f-string SQL, grep verifies) |
| T8 | Утечка секретов в логах | `httpx`/`httpcore` loggers → WARNING (иначе BOT_TOKEN в URL) |
| T9 | Открытый PG | DATABASE_URL — `postgres.railway.internal` |
| T10 | Webhook без secret | `WEBHOOK_SECRET_TOKEN` проверяется в `main.py:140` |
| T11 | PDF поломан / XSS | WeasyPrint sanitization (pytest не покрывает — отложено) |

## 12. Деплой

### 12.1 Railway prod

- **Builder**: Dockerfile
- **startCommand**: `python -m src.main` (uvicorn binds `PORT` env)
- **preDeployCommand**: `alembic upgrade head` (auto-migrate)
- **healthcheckPath**: `/health`, timeout 30s
- **restartPolicy**: ON_FAILURE, maxRetries=3
- **Volumes**: `/var/data/checkups` (для PDF)

При rolling deploy: новый контейнер запускается → `set_webhook` → старый получает SIGTERM → lifespan finally **не вызывает delete_webhook** (исправлено 17.05.2026, PR #27).

### 12.2 Локальная разработка

```bash
cp .env.example .env  # заполнить BOT_TOKEN, ANTHROPIC_API_KEY минимум
docker compose up -d postgres redis
.venv312/bin/alembic upgrade head
.venv312/bin/python -m src.main  # polling mode (WEBHOOK_BASE_URL пустой)
```

## 13. Тестирование

```bash
.venv312/bin/pytest -q  # → 165 passed, 1 skipped
```

36 файлов в `tests/`:
- `test_*_sanitize.py`, `test_scope_guard.py`, `test_admin_auth.py`, `test_admin_session.py` — security
- `test_checkup_*.py` — 20 вопросов content + quality + report
- `test_pricing_consistency.py` — цены 9000/14000/25000 не выдуманы
- `test_global_error_handler.py` — fallback на DB/reply failure
- `test_webhook_handler.py` — non-blocking webhook (PR #25)
- `test_lifespan_keeps_webhook.py` — `delete_webhook` не возвращается (PR #27)
- `test_alembic_env_url.py` — env.py использует psycopg3 dialect (PR #26)
- `test_httpx_loglevel.py` — httpx logger в WARNING (PR #28)
- `test_callback_uuid_safety.py` — `_safe_uuid` отвергает мусор (PR #24)
- `test_imports.py` — smoke на все импорты
- остальные — unit на чистые функции

Conftest подставляет SQLite in-memory для async session. **1 skipped тест** требует прод-Postgres.

### LLM regression
`python tests/run_regression_v3_1.py [--smoke | --critical]` — отдельный пакет, использует `tests/sycophancy_pack.json` + `adversarial_pack.json`.

## 14. Pricing & business flags

- Чекап Base = **9 000 ₽** (`AUDIT_AMOUNT_RUB`)
- Чекап Plus = **14 000 ₽** (`AUDIT_PLUS_AMOUNT_RUB`) — Base + видео-разбор от Кати
- Спринт = **25 000 ₽** — лист ожидания (не продаётся через бота)
- Окно возврата: 14 дней с `payment_succeeded_at` (`refund_eligible_until`)
- LLM stage прогрессия: `cold` → `warm` → `hot` (на основе messages_log)
- `VITACONSULT_PUBLIC` = false до 22.05.2026 (NDA, не упоминаем клиента в публичных ответах)

## 15. Известные ограничения / improvement plan

Полный список — `docs/qa_audit_2026-05-17/improvement_plan.md`. Кратко:

- **P1 latent**: yookassa idempotency (`audit.py:507` — нет SELECT перед INSERT в Payment; не блокер, т.к. yookassa выключен)
- **P1 latent**: FSM state cleanup (`audit.py`, `checkup.py` — KEY_APP_ID/KEY_PLAN не очищаются после завершения; новые сценарии перезапишут)
- **P2**: PDF generation не покрыт pytest (нужен Docker-build с WeasyPrint)
- **P2**: end-to-end FSM тесты на реальном Postgres (сейчас SQLite-in-memory)
- **P2**: глобальный LLM cost cap (есть per-user quota, нет глобального)
- **P3**: `/version` команда для самопроверки версии в проде
- **P3**: ConversationHandler миграция вместо ручного `context.user_data` FSM
- **Long-term**: Sentry SDK для real-time alerts, GitHub Actions CI, A/B на CTA меню

## 16. Гайдлайны для изменений

1. **Single source of truth для prices**: `audit.py:AUDIT_AMOUNT_RUB` + `audit.py:AUDIT_PLUS_AMOUNT_RUB`. Изменение → обновить `test_pricing_consistency.py` и оферту.
2. **Любая новая команда** регистрируется в `src/bot/handlers/__init__.py:register()`. Без регистрации не работает.
3. **Любой новый event** пишется в `events` table через `log_event(session, user_id, event, payload)`. Не использовать сырой `session.add(Event(...))` если возможно.
4. **Новый PD-поле** в `User` → обновить `pd_sanitize.py` (если может попасть в текст) + `privacy.export_my_data_command` (JSON-выгрузка).
5. **Не пиши f-string SQL**: только SQLAlchemy ORM или `bindparams`. Регрессия — `grep -rn 'f".*SELECT' src/` должен быть пустым.
6. **Не вызывай `delete_webhook` в lifespan**: тест `test_lifespan_keeps_webhook.py` упадёт.
7. **Не возвращай httpx logger на INFO**: тест `test_httpx_loglevel.py` упадёт.
8. **Миграции**: добавлять только аддитивные (`CREATE TABLE`, `ADD COLUMN NULLABLE`). Деструктивные (`DROP`, `ALTER TYPE`) — только после CSV-снапшота прода и явного OK от пользователя.
9. **PR процесс**: ветка `claude/<feature>` → push → пользователь сам открывает PR на GitHub → merge только с явным «ok» от пользователя.
10. **Старые ТЗ (`BOT_TZ.md`, `BOT_TZ_v3.md`) не править**: они исторические. Изменения функционала — сразу в этом `CLAUDE.md`.

---

_Версия документа: 1.0_
_Последнее обновление: 2026-05-17 23:00 МСК (Claude Sonnet 4.6)_
_Прод-состояние: alembic_version=0007_checkup_answers; webhook=active; pytest=165/0._
