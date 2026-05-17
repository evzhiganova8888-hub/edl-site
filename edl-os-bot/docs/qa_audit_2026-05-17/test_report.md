# Test report — QA audit 2026-05-17

> Сессия: targeted smoke + P0 диагностика (Опция B).
> Объём: ~15% от объёма ТЗ §6 (полные ~110 кейсов — отложены, см. `improvement_plan.md`).

## Резюме

| Метрика | Значение |
|---------|----------|
| pytest total | **153 passed, 1 skipped** |
| Новых тестов в этом PR | **+13** (было 140) |
| Файлов изменено | 3 src + 3 tests + 5 docs |
| P0 фиксов | 2 (webhook setup, db_url normalization) |
| P1 фиксов | 1 (UUID safety в 8 callsites) |

---

## Что проверено (новые регрешн-тесты)

### `tests/test_db_url_normalization.py` (4 теста)

Закрывает **P0-2** (latent). Проверяет, что `get_engine()` использует `normalized_database_url` (а не raw `database_url`), и что нормализация работает для всех вариантов:
- `postgresql://...` → `postgresql+asyncpg://...`
- `postgresql+asyncpg://...` → идемпотентно
- `sqlite+aiosqlite:///:memory:` → проходит как есть
- `get_engine()` действительно вызывает property, а не строку

### `tests/test_global_error_handler.py` (4 теста)

Закрывает регрессию **P0-1** (защита fallback от «бот ничего не отвечает»). Проверяет:
- handler отправляет «Что-то пошло не так» юзеру
- handler не падает при отказе DB (log_event raises)
- handler не падает при отказе reply (юзер заблокировал бота)
- handler не падает на non-Update объекте (фон job_queue)

### `tests/test_callback_uuid_safety.py` (5 тестов)

Закрывает **P1-1** (UUID parse). Проверяет:
- `_safe_uuid` возвращает None на garbage / empty / None / SQL-injection-like
- `_safe_uuid` парсит валидный UUID
- `refund:request:<garbage>` → юзер получает REFUND_NO_ACTIVE, не падает
- `checkup:start:<garbage>` → handler тихо возвращается
- `checkup:start` (без UUID) → handler тихо возвращается

---

## Что проверено ручным spot-check

| Модуль | Что проверено | Результат |
|--------|---------------|-----------|
| [handlers/__init__.py](../../src/bot/handlers/__init__.py) | Регистрация 22 commands + 19 callback patterns. Дубликатов нет | ✅ |
| [bot/handlers/start.py](../../src/bot/handlers/start.py) | `_send_main_menu` — атомарный reply_text, не может частично упасть | ✅ |
| [bot/handlers/bugs.py](../../src/bot/handlers/bugs.py) | `is_admin()` check в начале команды, защищает все ветки | ✅ |
| [core/working_hours.py](../../src/core/working_hours.py) | tz-aware datetime через `now_msk()`, корректные RF_HOLIDAYS на 2026–2027 | ✅ |
| [bot/handlers/refund.py](../../src/bot/handlers/refund.py) | После фикса — `_safe_uuid` отвергает malformed | ✅ |
| [bot/handlers/checkup.py](../../src/bot/handlers/checkup.py) | После фикса — все 7 UUID-parse sites защищены | ✅ |
| [bot/handlers/audit.py](../../src/bot/handlers/audit.py) | UUID parse только в helpers, которые получают из доверенных источников (`str(app.id)` / FSM) | ✅ |

---

## Что НЕ проверено (явный gap)

| Область ТЗ | Причина |
|------------|---------|
| §6.1 — полный flow `/start` для всех 7 deep-links | Только smoke (`?start=audit`); остальные 6 deep-links не покрыты тестами |
| §6.2 — quiz scoring правильность (24 вопроса, weighted) | Только что не падает на out-of-range |
| §6.3 — `/audit` full flow с lead capture | Только что UUID parse безопасен |
| §6.4 — `/checkup` 20 вопросов + PDF generation | PDF код вообще не тестируется в pytest (WeasyPrint в Dockerfile) |
| §6.5 — `/refund` 14-дневное окно edge cases | Только smoke |
| §6.6 — `/admin` все 8 sub-commands | Только smoke |
| §6.7–§6.18 — остальные | Не покрыто |
| §7 негативные кейсы (rate-limit, длинные тексты, спам) | Не проверены в этой сессии |
| §8 безопасность (SQL injection, XSS в bug-report, PD leakage) | Spot-check показал `_safe_uuid` + `validate_user_text` + `pd_sanitize` — но полная penetration не делалась |
| §9 perf (concurrent users, DB connection pool) | Не делалось |

---

## Manual production verification — required

После применения [RAILWAY_WEBHOOK_SETUP.md](RAILWAY_WEBHOOK_SETUP.md):

1. Послать `/start` → получить только меню, без «Что-то пошло не так».
2. Дождаться следующего деплоя Railway (например, push в main) → проверить Railway logs на отсутствие `409 Conflict`.
3. Проверить, что в логах появляется `Starting in WEBHOOK mode. URL=...` вместо warning о polling.
4. Проверить через `getWebhookInfo` (см. [RAILWAY_WEBHOOK_SETUP.md](RAILWAY_WEBHOOK_SETUP.md) Шаг 5), что webhook реально установлен.

---

## Pytest output

```
$ pytest -q
............................................. (153 dots)
153 passed, 1 skipped in 11.02s
```

Skipped — единственный тест требует прод-Postgres ([tests/test_admin_session.py:?]), а conftest подменяет на in-memory SQLite.
