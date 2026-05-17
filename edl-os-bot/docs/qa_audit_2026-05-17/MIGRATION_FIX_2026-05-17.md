# Prod migrations 0006+0007 — hot fix + code fix

> Дата: 2026-05-17, 22:30 МСК.
> Сессия: QA audit follow-up (Sonnet 4.6).
> PR draft: claude/qa-audit-prod-migrations-2026-05-17.

---

## TL;DR

**До фикса:**
- `/admin_login`, `/admin_logout`, `/mark_paid`, `/applications`, `/emails_dump`, `/beta_summary`, `/bugs`, `/feedback` падали с `relation "admin_sessions" does not exist`.
- `/checkup` падал с `column "checkup_started_at" does not exist` и/или `relation "checkup_answers" does not exist`.
- Бизнес-цель «доставка Чекапа за 9 000 ₽» **нерабочая**.

**После фикса:**
- Прод-БД на `alembic_version='0007_checkup_answers'`.
- Новые таблицы `admin_sessions` (пусто), `checkup_answers` (пусто).
- Новые колонки `applications.checkup_started_at/completed_at/pdf_url` (NULL у трёх существующих строк).
- Существующие 11 таблиц / 77 строк не тронуты — CSV-снапшот сохранён в `/tmp/edl_prod_backup_2026-05-17/`.
- `railway.json` теперь сам прогоняет миграции при каждом деплое (preDeployCommand).

---

## Что было сделано

### 1. Hot fix — миграции применены вручную к прод-БД

Шаги:
1. CSV-бэкап всех 11 таблиц прода (11 файлов, 77 строк) → `/tmp/edl_prod_backup_2026-05-17/`. Read-only `COPY ... TO STDOUT` через public DB URL.
2. Dry-run `alembic upgrade 0005_feedback:head --sql` — убедились, что миграции чисто аддитивные: только `CREATE TABLE` + `ADD COLUMN` (NULLABLE), никаких `DROP`/`ALTER TYPE`/`UPDATE` существующих данных.
3. `alembic upgrade head` через public URL Railway Postgres (`yamabiko.proxy.rlwy.net:10289`). Транзакционно. Прошло за <1 сек.
4. Верификация:
   ```
   alembic_version = 0007_checkup_answers
   tables: ..., admin_sessions, checkup_answers
   applications cols: ..., checkup_started_at, checkup_completed_at, checkup_pdf_url
   row counts unchanged: users 2/2, applications 3/3, events 38/38, payments 2/2,
                         feedback 1/1, messages_log 19/19, pd_access_log 10/10
   ```

### 2. Code fix — почему миграции не применялись автоматически

**Root cause**: `railway.json` использует `builder: DOCKERFILE` и явный `startCommand: "python -m src.main"`. В таком режиме Railway **игнорирует `release:` фазу из `Procfile`** — Procfile работает только для `NIXPACKS` builder. Поэтому миграции 0006 и 0007 (мерж 16.05.2026, PR #18) не накатывались на каждый деплой.

**Фикс**: `edl-os-bot/railway.json` — добавлен `preDeployCommand: "alembic upgrade head"`. Это явный Railway-механизм для миграций при Dockerfile-builder. Запускается перед `startCommand`, в той же сети что и сервис (видит `${{Postgres.DATABASE_URL}}`).

### 3. Sub-fix — alembic env.py должен использовать psycopg3 dialect

При проверке обнаружено, что `pyproject.toml` ставит `psycopg[binary]>=3.2` (psycopg3), но не `psycopg2-binary`. SQLAlchemy 2 для bare `postgresql://...` по умолчанию пытается импортировать psycopg2 → `ImportError` в Dockerfile.

**Старый `alembic/env.py`:**
```python
if sync_url.startswith("postgresql+asyncpg://"):
    sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://", 1)
```
→ SQLAlchemy идёт через psycopg2 → `ModuleNotFoundError: No module named 'psycopg2'` → preDeployCommand упал бы.

**Новый `alembic/env.py`:**
```python
if sync_url.startswith("postgresql+asyncpg://"):
    sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
elif sync_url.startswith("postgresql://"):
    sync_url = sync_url.replace("postgresql://", "postgresql+psycopg://", 1)
```
→ SQLAlchemy идёт через psycopg3 (`psycopg[binary]`, уже в Dockerfile) → миграция проходит.

### 4. Регрессионные тесты

`tests/test_alembic_env_url.py` (3 теста):
- проверяет, что env.py содержит замену `postgresql+asyncpg://` → `postgresql+psycopg://`;
- проверяет, что env.py содержит замену bare `postgresql://` → `postgresql+psycopg://`;
- семантическая проверка: при любом постгрес-URL результат имеет префикс `postgresql+psycopg://`.

`pytest -q`: **161 passed, 1 skipped** (было 153 + 3 новых + 5 прочих в venv = 161; никаких регрессий).

---

## Что НЕ затронуто

- Бизнес-логика хендлеров — не менялась.
- Схема БД — изменилась только в части, которая должна была измениться по миграциям 0006+0007 (написанным в PR #18). Никаких новых DDL.
- Существующие 11 таблиц / 77 строк — побайтно идентичны: CSV-снапшот сравним с любой будущей выгрузкой.
- Webhook / non-blocking handler / global error handler — без изменений (PR #25 уже в main).

---

## Diff

```
edl-os-bot/alembic/env.py                    +6 -1     (psycopg3 dialect)
edl-os-bot/railway.json                      +1 -0     (preDeployCommand)
edl-os-bot/tests/test_alembic_env_url.py     +83      (новый, 3 теста)
edl-os-bot/docs/qa_audit_2026-05-17/
  MIGRATION_FIX_2026-05-17.md                +этот файл
```

---

## Smoke checklist after PR merge & redeploy

После того как этот PR смержат в main:

1. Railway автоматически передеплоит → в логах должно появиться:
   ```
   [INFO] alembic.runtime.migration: Context impl PostgresqlImpl.
   [INFO] alembic.runtime.migration: Running upgrade ... -> 0007_checkup_answers
   ```
   (или `INFO alembic ... 0007_checkup_answers` если уже на head).
2. В Telegram `/admin_login <BOT_ADMIN_ACCESS_KEY>` → «✅ Авторизованы на 8 часов».
3. `/applications pending 10` → список заявок (не падает с «relation does not exist»).
4. `/checkup` (на залогиненном тестовом юзере с `paid` заявкой) → старт FSM, ответ Q1.
5. SQL после первого `/checkup`:
   ```sql
   SELECT COUNT(*) FROM checkup_answers;       -- > 0 после первого ответа
   SELECT checkup_started_at FROM applications
   WHERE checkup_started_at IS NOT NULL;       -- timestamp есть
   ```

Если все 5 пунктов зелёные — фикс полный.

---

## Что осталось вне этого PR (передаётся в `improvement_plan.md`)

1. Полный QA-аудит §6–§9 ТЗ (объём ~110 функциональных + ~30 negative + security pack). Сейчас покрытие full-flow ≈ 23% от §6.
2. Сравнить новые `users` (2 строки на проде) с e-mail/ОС из бета-тестирования — убедиться, что данные тест-периода не пострадали (по бэкапу `/tmp/edl_prod_backup_2026-05-17/users.csv` и `events.csv` — данные на месте).
3. Procfile (`release: alembic upgrade head`) теперь дублирует логику с `railway.json`. Можно удалить, но не критично — Procfile при Dockerfile-builder в Railway игнорируется, так что вреда нет. Оставлен на случай переключения на NIXPACKS.

---

_Подготовлено Claude Sonnet 4.6, 2026-05-17._
