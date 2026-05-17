# Bug log — QA audit 2026-05-17

> Сессия: smoke + targeted P0 диагностика (Опция B).
> Полный аудит §6–§9 ТЗ отложен (см. `improvement_plan.md` §1).

## Условные обозначения

- **P0** — бот падает / тихий отказ / потерянные деньги. Чинить немедленно.
- **P1** — деградация UX / неверные данные. Чинить в спринт.
- **P2** — косметика / мелочи. Чинить when convenient.

---

## P0 — закрыты в этом PR

### P0-1. «menu + error»: бот отвечает и меню, и ошибкой на /start, /menu

- **Воспроизведение** (наблюдение Евгении 17.05.2026 17:26 МСК): отправка `/start` или `/menu` → бот шлёт **и** главное меню, **и** «Что-то пошло не так на нашей стороне. Я уже сообщил команде.»
- **Root cause**: бот на Railway работает в polling mode (`WEBHOOK_BASE_URL` не задан). При деплое Railway не убивает старый контейнер до запуска нового. Оба инстанса параллельно вызывают `getUpdates` → **409 Conflict** ([логи Railway](../../README.md), 17:42:34 UTC). Telegram отдаёт один и тот же апдейт обоим инстансам через окно перекрытия → старый обработчик успевает отправить меню, новый падает на DB или другом ресурсе и попадает в `_global_error_handler`.
- **Доказательства**:
  - Railway logs: `telegram.error.Conflict: terminated by other getUpdates request; make sure that only one bot instance is running`
  - Архитектурный анализ: [src/main.py:64–66](../../src/main.py#L64) запускает polling всегда, кроме случая когда выставлен `WEBHOOK_BASE_URL`.
  - Код `_send_main_menu` ([src/bot/handlers/start.py:108–110](../../src/bot/handlers/start.py#L108)) — атомарный `reply_text`, не может в одной инвокации и успеть, и упасть. Значит апдейт обрабатывается дважды.
- **Фикс**: переход на webhook mode. Инфраструктура уже в `main.py:55–63` — нужно только выставить env var. См. [RAILWAY_WEBHOOK_SETUP.md](RAILWAY_WEBHOOK_SETUP.md). После активации 409 Conflict исчезнут, race условие невозможно.
- **Регрешн**: [tests/test_global_error_handler.py](../../tests/test_global_error_handler.py) — 4 теста, что fallback не падает при отказе БД / reply / non-Update.

---

### P0-2. (латент) `session.py` игнорирует `normalized_database_url`

- **Воспроизведение**: если на Railway `DATABASE_URL=postgresql://...` (без `+asyncpg`), `create_async_engine` падает с `No module named 'psycopg2'` или `InvalidRequestError: asyncio extension requires async driver`.
- **Root cause**: [src/db/session.py:14](../../src/db/session.py#L14) (до фикса) использовал `settings.database_url` напрямую, минуя `settings.normalized_database_url` property из [src/core/config.py:99–104](../../src/core/config.py#L99) — она нигде не вызывалась (grep подтверждает 0 callsites).
- **Статус в проде**: не проявляется — Railway почему-то передаёт уже корректный URL. Но **латент**: любое изменение Railway-конфига или миграция на другой хостинг — баг проявится. Это и есть «P0-latent».
- **Фикс**: одна строка → `settings.normalized_database_url`.
- **Регрешн**: [tests/test_db_url_normalization.py](../../tests/test_db_url_normalization.py) — 4 теста (postgresql → normalized, idempotent, sqlite passthrough, `get_engine()` использует normalized).

---

## P1 — закрыты в этом PR

### P1-1. UUID parse без try-except в callbacks

- **Воспроизведение**: callback с искажённым UUID (`refund:request:not-a-uuid` или `checkup:start:not-a-uuid`) → `ValueError` → `_global_error_handler` → юзер видит «Что-то пошло не так».
- **Когда срабатывает**: устаревшая клавиатура после деплоя; кастомный Telegram-клиент; внутренний баг в `keyboards.py`, если кто-то случайно положит туда не-UUID.
- **Фикс**:
  - [refund.py:78–88](../../src/bot/handlers/refund.py#L78) — обёрнут try-except, при ValueError → `texts.REFUND_NO_ACTIVE` + меню (то же что и для несуществующей заявки).
  - [checkup.py:42–53](../../src/bot/handlers/checkup.py#L42) — добавлен helper `_safe_uuid()`. Все 7 callsites `UUID(app_id_str)` заменены на `_safe_uuid(...)` + early return при None.
- **Регрешн**: [tests/test_callback_uuid_safety.py](../../tests/test_callback_uuid_safety.py) — 5 тестов.

---

## P1 — отложены (см. `improvement_plan.md`)

### P1-2. (латент) yookassa payment double-insert

- **Файл**: [audit.py:507–517](../../src/bot/handlers/audit.py#L507).
- **Воспроизведение**: при `PAYMENT_MODE=yookassa` (сейчас выключен), повторное нажатие на кнопку «Оплатить» создаёт две `Payment` строки с одним `inv_id`.
- **Защита глубиной**: вероятно есть UNIQUE constraint в БД на `provider_invoice_id`. Если нет — двойная строка может корраптить аналитику.
- **Не блокирует прод**: yookassa на модерации, активируется не раньше июня 2026.
- **План**: добавить idempotency-проверку (`SELECT ... WHERE provider_invoice_id=...` перед `session.add()`) до активации yookassa.

### P1-3. (латент) FSM-ключи не чистятся при completion

- **Файлы**: [audit.py:328](../../src/bot/handlers/audit.py#L328) (только `KEY_FLOW`, не `KEY_APP_ID`/`KEY_PLAN`); [checkup.py:212](../../src/bot/handlers/checkup.py#L212) (никакие ключи не чистятся после `_finalize_checkup`).
- **Влияние**: при повторном запуске сценария может остаться "хвост" предыдущей сессии в `context.user_data`. Не критично (новые значения перезапишут старые), но мешает дебагу.
- **План**: добавить `_clear_state(context)` в конце каждого FSM-сценария.

### P1-4. Duplicate event log в `/mark_paid` на повторный вызов

- **Файл**: [admin.py:214–224](../../src/bot/handlers/admin.py#L214).
- **Влияние**: повторный `/mark_paid <uuid>` логирует событие `payment_marked_paid` дважды, хотя БД-обновление идемпотентно.
- **План**: проверить `result.get("already_paid")` **до** `log_event`.

---

## P2 — не чинятся в этом PR (только перечислены)

- `admin_login.py:100–102` — `session.commit()` без изменений в сессии (мёртвый код).
- `admin.py:234–240` — повторный локальный импорт `keyboards` внутри функции при наличии import на верхнем уровне.
- `refund.py:52–56` — `refund_eligible_until` нейминг (правильно работает, но семантика читается с натяжкой).
- `quiz.py:71–72` — early return при `index >= len(QUIZ_QUESTIONS)` без сброса FSM ключей (юзер может «застрять» в квизе → `/reset` чинит).

---

## False positives (Explore-агент выдал, ручная верификация опровергла)

| Файл | Symptom (claim) | Реальность |
|------|-----------------|------------|
| `bugs.py:33–40` | Admin check отсутствует для `/bugs export` | Check выполняется ДО разбора `args` |
| `audit.py:402` | `update.effective_message` может быть None в callback | PTB гарантирует `callback_query.message` |
| `audit.py:398/450/475/491` | UUID parse от user-controlled callback | UUID берётся из `str(app.id)` (DB) или `user_data[KEY_APP_ID]` (FSM), не из callback_data |
| `working_hours.py:55` | naive datetime ломает `is_working_now` | Все callers передают tz-aware через `now_msk()` |
