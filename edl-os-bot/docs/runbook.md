# Runbook: EDL OS Bot — типовые проблемы

> Версия: 2026-05-17. Стек: Railway + python-telegram-bot 21 + FastAPI + Postgres + Redis.

---

## 1. Бот не отвечает в Telegram

**Симптомы**: отправляешь `/start` — тишина.

**Шаги диагностики:**

1. Railway → `edl-site` → **Deployments** → последний → статус.
   - `Active` — сервис живёт, иди к п.2.
   - `Failed` / `Crashed` — смотри логи (п.4 ниже).

2. В логах найти строку `Polling started`.
   - Если нет — polling не запустился. Проверить `BOT_TOKEN` (Railway → Variables → глаз).

3. Проверить healthcheck:
   ```
   curl https://edl-site-production.up.railway.app/health
   ```
   Ожидаем `{"status":"ok",...}`. Если 502 — сервис упал.

4. Смотреть логи Railway → `edl-site` → Deployments → клик на деплой → **View logs**.
   Искать: `Traceback`, `RuntimeError`, `ConnectionRefusedError`.

**Частые причины:**
- `BOT_TOKEN is not set` → добавить/исправить в Railway Variables.
- `asyncpg.InvalidPasswordError` → неверный `DATABASE_URL`.
- `redis.exceptions.ConnectionError` → неверный `REDIS_URL` или Redis не запущен.

---

## 2. Healthcheck падает (деплой не проходит)

**Симптомы**: Railway показывает `Healthcheck failure`, сервис не переходит в Active.

**Диагностика:**

1. Убедиться, что `PORT` не задан вручную в Railway Variables — Railway инжектит его сам.
   Uvicorn читает `PORT` из env (с фолбеком 8000) — см. `src/main.py:main()`.

2. Проверить `Dockerfile` на наличие `HEALTHCHECK` директивы.
   Railway использует собственный HC (path `/health`, timeout 300s).

3. Логи старта — если lifespan рухнул (ошибка до `yield`) → HC всегда 503.
   Искать исключение в первых 50 строках лога деплоя.

4. Если `/health` возвращает 503 с телом `Bot is not ready` → lifespan прошёл, но
   `_ptb_app` не инициализировался. Причина — неверный `BOT_TOKEN` (Telegram отклонил).

---

## 3. /admin_login не работает

**Симптомы**: отвечает «Неверный ключ» или «Слишком много попыток».

**Диагностика:**

1. **«Неверный ключ»**:
   - Railway → Variables → `BOT_ADMIN_ACCESS_KEY` → кликнуть глаз, скопировать значение.
   - Сравнить посимвольно с тем, что вводишь. Пробелы? Переносы строки?

2. **«Слишком много попыток»** (rate-limit):
   - Redis rate-limit: 3 попытки / 10 мин → блок 1 час.
   - Сбросить блок: подключиться к Redis → `DEL ratelimit:admin_login:<user_id>`.
   - Или подождать 1 час.

3. **`REDIS_URL` не задан** → rate-limit падает при старте → `/admin_login` может не работать.
   Добавить `REDIS_URL = ${{Redis.REDIS_URL}}` в Variables.

4. **Пользователь не в `ADMIN_USER_IDS`** → auth всегда отказывает.
   Добавить `tg_user_id` в переменную через запятую.

---

## 4. Оплата не фиксируется (PAYMENT_MODE=stub)

**Симптомы**: юзер говорит «заплатил», а заявка в `awaiting_manual_payment`.

**Нормальный флоу (stub)**:
1. Юзер завершает анкету → заявка `awaiting_manual_payment` → бриф в `ADMIN_CHAT_ID`.
2. Иван выставляет счёт вручную (реквизиты / ЮKassa ссылка напрямую).
3. Иван фиксирует: `/mark_paid <UUID> <сумма> <invoice_id>`.
4. Бот шлёт юзеру «Оплата подтверждена», открывает `/checkup`.

**Если бриф не пришёл в ADMIN_CHAT_ID:**
- Убедиться, что бот добавлен в чат как участник.
- Проверить `ADMIN_CHAT_ID` — должен быть числовой ID (с минусом для групп, напр. `-1001234567890`).
- Получить ID: переслать любое сообщение из чата в `@userinfobot`.

---

## 5. Миграции не применились

**Симптомы**: таблицы `admin_sessions` / `checkup_answers` отсутствуют в БД.

**Диагностика:**
```sql
SELECT version_num FROM alembic_version;
```
Ожидаем `0007_checkup_answers`. Если меньше — release-фаза не отработала.

**Исправление:**

1. Railway → `edl-site` → Deployments → последний → найти лог `release:`.
2. Если `release:` отсутствует — проверить `Procfile`:
   ```
   release: alembic upgrade head
   web: python -m src.main
   ```
3. Убедиться что `SYNC_DATABASE_URL` задан (alembic нужен синхронный psycopg, не asyncpg).
4. Если `DuplicateTable` ошибка и миграция уже в БД:
   ```sql
   -- Только после ручного подтверждения!
   UPDATE alembic_version SET version_num='0007_checkup_answers';
   ```

---

## 6. PDF-отчёт Чекапа не генерируется

**Симптомы**: бот пишет «Отчёт готов», но PDF не приходит, или пишет об ошибке.

**Диагностика:**
- Логи: искать `WeasyPrintError`, `OSError`, `fontconfig`.
- WeasyPrint требует `fonts-dejavu`, `libpango`, `libcairo` — всё в `Dockerfile`.
- Путь хранения: `/var/data/checkups/` (Volume должен быть примонтирован в Railway).

**Если Railway Volume не создан:**
Railway → `edl-site` → Volumes → Add Volume → Mount path: `/var/data`.

---

## 7. Добавить нового администратора

1. Получить Telegram user_id нового человека (напр. через `@userinfobot`).
2. Railway → Variables → `ADMIN_USER_IDS` → дописать id через запятую.
3. Redeploy не нужен — переменная читается при каждом запросе через `settings.admin_user_ids`.

Но если хочешь дать доступ к `/admin_login` — также передать `BOT_ADMIN_ACCESS_KEY` лично.
