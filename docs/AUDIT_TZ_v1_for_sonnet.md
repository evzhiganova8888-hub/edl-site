# ТЗ: Полный аудит, тестирование и доведение экосистемы EDL OS до 10/10

> **Адресат**: Claude Sonnet 4.6 (в новом чате Claude Code, web/desktop).
> **Автор ТЗ**: Tech Lead 15+ лет (B2B SaaS / Telegram-боты / Railway / Python) + Senior QA.
> **Дата**: 2026-05-17.
> **Версия ТЗ**: v1.0.

---

## 0. КАК ЧИТАТЬ ЭТО ТЗ

ТЗ состоит из 11 разделов и идёт **строго по шагам**. Каждый шаг имеет:
- **Цель** — что должно стать «зелёным» в конце шага;
- **Действия** — конкретные команды/файлы/UI-клики;
- **Acceptance criteria (AC)** — как понять, что шаг завершён;
- **Если сломалось** — fallback / альтернативный путь.

**Никогда не пропускать раздел 1 (Контекст)** — без него все последующие шаги непонятны.

**Никогда не делать merge / push в `main` без явного подтверждения пользователя** (Евгении). Все правки — через отдельные ветки и draft PR.

**Все таймауты на сетевые операции** — ретраи 4 раза с экспоненциальным бэкоффом (2s, 4s, 8s, 16s).

---

## 1. КОНТЕКСТ ЭКОСИСТЕМЫ

### 1.1 Состав

| Компонент | URL / Локация | Стек |
|---|---|---|
| **Сайт (лендинг)** | https://elephantdreams.ru (GitHub Pages, CNAME) | Статический HTML/CSS/JS |
| **Telegram-бот** | @edl_os_bot | Python 3.12, python-telegram-bot 21, FastAPI, SQLAlchemy 2 async |
| **Хостинг бота** | Railway, проект `efficient-appreciation`, env `production`, сервис `edl-site` | Docker, Postgres, Redis |
| **БД** | Railway Postgres (internal URL) | PostgreSQL 16 + alembic |
| **Кэш / rate-limit** | Railway Redis | redis 7 |
| **LLM** | Claude через прокси `https://api.proxyapi.ru/anthropic` | Anthropic SDK |
| **Платежи** | YooKassa (dormant) + Stub (active в проде) | Ручное /mark_paid |
| **Аналитика сайта** | inline-JS трекер → localStorage → Google Apps Script | См. `analytics-manifest.json` |
| **Репозиторий** | https://github.com/evzhiganova8888-hub/edl-site | Monorepo: сайт + `edl-os-bot/` |

### 1.2 Текущая боль (что сломано)

1. **🔴 БЛОКЕР**: Новые деплои на Railway падают на `Healthcheck failure (00:53)`. Корневая причина — `src/main.py:121` слушает захардкоженный `port=8000`, а Railway инжектит `$PORT` (обычно 8080) и роутит HC именно туда. Старый деплой (до PR #18) ещё работает, бот отвечает в polling.
2. **🔴 БЛОКЕР**: В Railway Variables **нет `REDIS_URL` и `BOT_ADMIN_ACCESS_KEY`** — без них `/admin_login` всегда отказывает (rate-limit падает, ключа нет → константное сравнение всегда false).
3. **🟡 Важно**: Миграции `0006_admin_sessions` и `0007_checkup_answers` не применены в проде (в `alembic_version` стоит `0005_feedback`). Без них не работает админ-сессия и Чекап не сохраняет ответы. Применятся автоматически через `release: alembic upgrade head` после успешного деплоя.
4. **🟡 Важно**: Нужно убедиться, что `DATABASE_URL` указывает на **internal** Railway URL (`*.railway.internal`), а не публичный.
5. **🟢 Гигиена**: Не выставлены `PAYMENT_MODE`, `OFFER_CHECKUP_URL`, `PRIVACY_POLICY_URL`, `SITE_URL` (есть код-дефолты, но лучше явно).

### 1.3 Известные коммиты

- `647ba27` — Merge PR #19 (Dockerfile fix, **БЕЗ PORT fix** — PORT-фикс из контекста предыдущего чата так и не был запушен).
- `42b94bb` — Сам Dockerfile fix (Debian 12 / WeasyPrint 63+).
- `f3589e6` — Merge PR #18 (Чекап v3.2, миграции 0006/0007, admin commands).
- Активная ветка для этой работы: `claude/review-railway-deployment-ADdCP`.

### 1.4 Доступы и инструменты

- **GitHub MCP** доступен (только репозиторий `evzhiganova8888-hub/edl-site`). Используй `mcp__github__*` инструменты — `gh` CLI **не доступен**.
- **Railway UI** — у пользователя. Все действия в Railway = инструкция пользователю.
- **Railway CLI** — не доступен из контейнера. Все правки переменных — через UI или через `railway login` локально у пользователя.
- **Bash** — есть, песочница ephemeral; коммитить и пушить нужно.
- **WebFetch/WebSearch** — есть.

---

## 2. ШАГ 1. Снятие блокера деплоя (PORT env var)

### 2.1 Цель
Новый деплой проходит Healthcheck зелёным и сервис `edl-site` переходит в статус Active.

### 2.2 Действия

1. **Создать ветку** от `main`:
   ```bash
   git fetch origin main
   git checkout -b fix/deploy-port-from-env origin/main
   ```

2. **Править `edl-os-bot/src/main.py`** — функция `main()` в конце файла (около строки 117-125). Заменить:

   ```python
   def main() -> None:
       uvicorn.run(
           "src.main:api",
           host="0.0.0.0",
           port=8000,
           log_level=settings.log_level.lower(),
           reload=settings.environment == "development",
       )
   ```

   на:

   ```python
   def main() -> None:
       import os
       port = int(os.environ.get("PORT", "8000"))
       uvicorn.run(
           "src.main:api",
           host="0.0.0.0",
           port=port,
           log_level=settings.log_level.lower(),
           reload=settings.environment == "development",
       )
   ```

   **Альтернатива (менее предпочтительная)**: добавить в `Settings` в `src/core/config.py` поле `port: int = 8000` (pydantic-settings сам подхватит `PORT` из env). Если так — `main()` использует `settings.port`. **Не делай оба варианта одновременно**.

3. **Коммит**:
   ```bash
   git add edl-os-bot/src/main.py
   git commit -m "fix(deploy): read PORT from env for Railway healthcheck

   Railway инжектит \$PORT и роутит health/traffic именно туда.
   Без этого Healthcheck (path /health) уходит на 8000 и таймаутит за 53 сек.
   "
   ```

4. **Push + draft PR**:
   ```bash
   git push -u origin fix/deploy-port-from-env
   ```
   Создать draft PR через `mcp__github__create_pull_request` с base=`main`, head=`fix/deploy-port-from-env`, draft=true.

### 2.3 Acceptance criteria

- [ ] PR создан как draft, ссылка отдана пользователю.
- [ ] В диффе PR — только один файл `edl-os-bot/src/main.py`, изменения минимальные (4-5 строк).
- [ ] Пользователь подтвердил merge → проверить через `mcp__github__pull_request_read` что PR смержен.
- [ ] Railway автоматически триггернул деплой (видно в Deployments).
- [ ] Healthcheck зелёный (статус строки Network › Healthcheck = ✓, не ✗).
- [ ] Сервис `edl-site` показывает status = Active.

### 2.4 Если сломалось

- **Build падает**: смотреть `mcp__github__list_commits` на main vs `mcp__github__get_commit` для последнего, проверить `Dockerfile`.
- **Healthcheck всё ещё красный**: открыть Deploy logs (Railway → edl-site → Deployments → клик на failed → View logs), искать что отвечает `/health`. Возможно `lifespan` упал на старте — тогда искать stack trace.
- **Сервис стартует, но `/health` 503 «Bot is not ready»**: проблема в `BOT_TOKEN` (не подхватывается из env). Перейти к шагу 3.

---

## 3. ШАГ 2. Аудит и приведение Railway Variables в порядок

### 3.1 Цель
Все переменные окружения выставлены, не содержат секретов в логах, ссылки на инфраструктуру через Railway references (`${{Postgres.DATABASE_URL}}`, `${{Redis.REDIS_URL}}`).

### 3.2 Полный список переменных (single source of truth)

Источник правды — `edl-os-bot/src/core/config.py:Settings`. Сводим в таблицу.

#### 3.2.1 КРИТИЧНЫЕ (без них бот не работает или работает с дырами)

| Переменная | Значение | Где в коде | Что ломается без неё |
|---|---|---|---|
| `BOT_TOKEN` | `<токен от @BotFather>` | `config.py:25`, `main.py:37` | Бот не стартует (`RuntimeError: BOT_TOKEN is not set`) |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | `config.py:36` + `normalized_database_url` | Все DB операции падают |
| `SYNC_DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (без `+asyncpg`) | `config.py:37` | `alembic upgrade head` упадёт |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` | `config.py:40`, `handlers/admin_login.py` | `/admin_login` rate-limit падает; FSM-сессии Чекапа потенциально |
| `ADMIN_USER_IDS` | `123456789,987654321` (через запятую) | `config.py:27`, `admin/auth.py` | Админ-команды отказывают всем |
| `ADMIN_CHAT_ID` | `-1001234567890` (id чата, куда бот добавлен) | `config.py:29`, `notifications.py` | Брифы заявок не доходят |
| `BOT_ADMIN_ACCESS_KEY` | сгенерировать: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` | `config.py:68`, `handlers/admin_login.py:93` | `/admin_login` всегда ❌ |
| `ANTHROPIC_API_KEY` | `<ключ proxyapi.ru или прямой Anthropic>` | `config.py:43`, `core/llm.py` | LLM-ответы не работают (бот молчит при свободном диалоге) |
| `ANTHROPIC_BASE_URL` | `https://api.proxyapi.ru/anthropic` | `config.py:46` | Идёт прямой запрос к Anthropic (если ключ российский — 403) |

#### 3.2.2 ВАЖНЫЕ (есть код-дефолты, но лучше явно)

| Переменная | Рекомендуемое значение | Зачем |
|---|---|---|
| `ENVIRONMENT` | `production` | Отключает `reload=True` в uvicorn |
| `LOG_LEVEL` | `INFO` | Уровень логов |
| `PAYMENT_MODE` | `stub` | Явно фиксируем режим ручной оплаты (YooKassa dormant) |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Зафиксировать модель, чтобы не съезжать на дороже |
| `ANTHROPIC_MAX_TOKENS` | `600` | Лимит ответа LLM |
| `ADMIN_SESSION_HOURS` | `8` | Длительность админ-сессии после /admin_login |
| `OFFER_URL` | `https://elephantdreams.ru/legal/offer.html` | Линк на оферту в кнопках |
| `OFFER_CHECKUP_URL` | `https://elephantdreams.ru/legal/offer-checkup-2026-05.html` | Линк на оферту Чекапа |
| `PRIVACY_POLICY_URL` | `https://elephantdreams.ru/legal/privacy.html` | Линк на политику ПД |
| `PRIVACY_POLICY_VERSION` | `2026-05-11` | Версия ПП, фиксируется в БД при согласии |
| `SITE_URL` | `https://elephantdreams.ru` | База ссылок |
| `CHANNEL_URL` | `https://t.me/edl_os` | Канал |
| `SALES_USERNAME` | `lvanKhudyakov` | username Ивана (без @) |
| `TIMEZONE` | `Europe/Moscow` | TZ для working hours |
| `WORKING_HOURS_START` | `10` | МСК часы работы (для авто-ответов) |
| `WORKING_HOURS_END` | `19` | МСК |

#### 3.2.3 НЕ ТРОГАТЬ (Python tunables — Railway сам подтянет)

| Переменная | Значение | Зачем |
|---|---|---|
| `PYTHONUNBUFFERED` | `1` | Логи в реальном времени (уже в Dockerfile ENV) |
| `PYTHONDONTWRITEBYTECODE` | `1` | Уже в Dockerfile |
| `PIP_NO_CACHE_DIR` | `1` | Уже в Dockerfile |
| `PIP_DISABLE_PIP_VERSION_CHECK` | `1` | Уже в Dockerfile |
| `PORT` | (НЕ ставить вручную) | Railway инжектит автоматически |

#### 3.2.4 ДЛЯ БУДУЩЕГО (YooKassa, когда модерация пройдёт)

| Переменная | Когда заполнять | Источник |
|---|---|---|
| `YOOKASSA_SHOP_ID` | После одобрения магазина | https://yookassa.ru → Магазины |
| `YOOKASSA_SECRET_KEY` | После одобрения | Там же → Интеграция |
| `WEBHOOK_BASE_URL` | Если переходим с polling на webhook | `https://edl-site-production.up.railway.app` |
| `WEBHOOK_SECRET_TOKEN` | вместе с webhook | `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |

#### 3.2.5 ВЫПИЛИТЬ (не используется в коде / устаревшее)

Аудит `grep`-ом по `edl-os-bot/src/` показал, что в текущем `config.py` **нет** упоминаний `VITACONSULT_PUBLIC` как env-переменной (это поле с дефолтом `False`, но в Railway скриншоте оно есть). Можно убрать из Railway, если не используется в `vitaconsult_public` фичефлаге. **Проверить grep**:
```bash
grep -rn "vitaconsult_public\|VITACONSULT_PUBLIC" edl-os-bot/src/
```
Если нет реальных условий — удалить переменную из Railway.

### 3.3 Действия

1. **Открыть Railway** → проект `efficient-appreciation` → env `production` → сервис `edl-site` → tab **Variables**.

2. **Для каждой переменной из 3.2.1 и 3.2.2**:
   - Если её нет — нажать **+ New Variable**, ввести имя и значение из таблицы.
   - Если есть — кликнуть глаз/раскрыть и **сверить значение** (для `DATABASE_URL`, `REDIS_URL` особенно — должны быть Railway references `${{Postgres.DATABASE_URL}}` и `${{Redis.REDIS_URL}}`, не публичные URL).

3. **Для `BOT_ADMIN_ACCESS_KEY`** — сгенерировать локально и записать в **1Password / sticky note Евгении**. После этого добавить в Railway. **НЕ постить ключ в чат и не коммитить.**

4. **Сохранить** (Railway сам триггернёт redeploy после изменения переменных — это нормально).

### 3.4 Acceptance criteria

- [ ] Все переменные из таблиц 3.2.1 и 3.2.2 присутствуют.
- [ ] `DATABASE_URL` содержит `railway.internal` (а не `.railway.app`).
- [ ] `REDIS_URL` содержит `railway.internal`.
- [ ] `BOT_ADMIN_ACCESS_KEY` ≥ 32 символа, base64url.
- [ ] `ANTHROPIC_BASE_URL` оканчивается на `/anthropic` (без trailing slash).
- [ ] Redeploy после изменения переменных прошёл успешно.
- [ ] В логах при старте видно `Polling started` (не webhook).

### 3.5 Если сломалось

- **`DATABASE_URL` показывает publicURL и нет ссылки на Postgres.DATABASE_URL**: открыть сервис Postgres → Connect → копировать `DATABASE_URL` (Private) или ввести вручную `${{Postgres.DATABASE_URL}}`.
- **Alembic падает в `release:`** с ошибкой `cannot connect`: проверить `SYNC_DATABASE_URL` — alembic использует синхронный psycopg, не asyncpg.

---

## 4. ШАГ 3. Проверка миграций БД

### 4.1 Цель
В Postgres присутствуют все 7 миграций и таблицы `admin_sessions` + `checkup_answers`.

### 4.2 Действия

1. **Дождаться** успешного деплоя после шагов 1-2.

2. **Открыть Railway → Postgres → tab Data** (или Connect → psql / любой PG-клиент через публичный URL).

3. **Проверить версию миграций**:
   ```sql
   SELECT version_num FROM alembic_version;
   ```
   Ожидаем: `0007_checkup_answers`.

4. **Проверить наличие таблиц**:
   ```sql
   SELECT table_name FROM information_schema.tables
   WHERE table_schema='public' ORDER BY table_name;
   ```
   Должно быть **13 таблиц** (было 11, +2):
   - `admin_sessions` (новая, миграция 0006)
   - `alembic_version`
   - `applications` (+ новые колонки `checkup_started_at`, `checkup_completed_at`, `checkup_pdf_url`)
   - `bot_errors`
   - `checkup_answers` (новая, миграция 0007)
   - `events`
   - `feature_flags`
   - `feedback`
   - `messages_log`
   - `payments`
   - `pd_access_log`
   - `refunds`
   - `users`

5. **Проверить новые колонки в `applications`**:
   ```sql
   SELECT column_name FROM information_schema.columns
   WHERE table_name='applications'
     AND column_name IN ('checkup_started_at', 'checkup_completed_at', 'checkup_pdf_url');
   ```
   Должно вернуть 3 строки.

### 4.3 Acceptance criteria

- [ ] `alembic_version.version_num = '0007_checkup_answers'`.
- [ ] Таблицы `admin_sessions` и `checkup_answers` есть.
- [ ] Колонки `checkup_*` в `applications` есть.

### 4.4 Если сломалось

- **Версия осталась `0005_feedback`** → release-фаза не отработала. Зайти в Railway → edl-site → Deployments → последний → найти лог `release:`. Если нет — проверить `Procfile`:
  ```
  release: alembic upgrade head
  web: python -m src.main
  ```
- **Alembic ругается на `DuplicateTable`** → миграция уже применилась, но `alembic_version` не обновился. **Не делать `downgrade`!** Вручную:
  ```sql
  UPDATE alembic_version SET version_num='0007_checkup_answers';
  ```
  Только после ручного подтверждения у пользователя.

---

## 5. ШАГ 4. Smoke-test бота (happy path)

### 5.1 Цель
Полный сценарий «новый пользователь → купил Чекап → прошёл 20 вопросов» работает end-to-end.

### 5.2 Подготовка

- Telegram-аккаунт пользователя должен быть в `ADMIN_USER_IDS` (его user_id).
- `ADMIN_CHAT_ID` = ID группы/чата, куда бот добавлен (для приёма брифов).
- `BOT_ADMIN_ACCESS_KEY` известен (из Шага 2).

### 5.3 Сценарий

| # | Действие | Ожидание | Что проверяем |
|---|---|---|---|
| 1 | `/start` в @edl_os_bot | Меню с 9 кнопками; в БД появилась запись в `users` | start.py + register_user |
| 2 | `/admin_login <BOT_ADMIN_ACCESS_KEY>` | `✅ Авторизованы как админ на 8 часов`; запись в `admin_sessions` | rate-limit + HMAC compare |
| 3 | Кнопка «Бизнес-чекап» или `/audit` | Бот ведёт по FSM: «Базовый / Стандарт / Премиум» → согласие ПД → ФИО → email → company → принять оферту | audit.py |
| 4 | Дойти до конца оферты | `Ждите счёт от Ивана. Он напишет в течение N часов.` (НЕ `Оплатить через YooKassa`) | PAYMENT_MODE=stub |
| 5 | В `ADMIN_CHAT_ID` пришёл бриф | Содержит UUID заявки, контакт, segment | notifications.py |
| 6 | `/applications pending 5` | Список заявок (минимум 1) | admin.py |
| 7 | `/mark_paid <UUID> 9000 test-001` | `✅ Помечена paid`; юзеру личка `Оплата подтверждена. /checkup` | admin.py /mark_paid |
| 8 | `/checkup` → Начать → ответить на 20 вопросов | Прогресс-бар 1/20 → 20/20, intro к каждому слою (4) | checkup.py FSM |
| 9 | По завершении | Сообщение «Отчёт готов» + PDF в чат (или ссылка на /var/data/checkups/...) | report.py |
| 10 | `/beta_summary` | Метрики беты (если есть данные) | admin.py |

### 5.4 Проверки в БД (после сценария)

```sql
-- Сколько ответов на чекап (должно быть 20 на одного application)
SELECT application_id, COUNT(*) FROM checkup_answers GROUP BY application_id;

-- Завершён ли чекап
SELECT id, checkup_started_at, checkup_completed_at, checkup_pdf_url
FROM applications WHERE checkup_completed_at IS NOT NULL;

-- Платежи
SELECT amount, status, invoice_id FROM payments ORDER BY created_at DESC LIMIT 5;

-- События (для аналитики)
SELECT event_type, COUNT(*) FROM events GROUP BY event_type ORDER BY COUNT(*) DESC;
```

### 5.5 Acceptance criteria

- [ ] Все 10 шагов сценария прошли без ошибок.
- [ ] В `events` записаны минимум: `start`, `consent_given`, `application_created`, `mark_paid`, `checkup_started`, `checkup_completed`.
- [ ] `checkup_answers` содержит 20 строк для тестовой заявки.
- [ ] PDF сгенерирован (есть в `/var/data/checkups/` или прислан в чат).
- [ ] В `bot_errors` нет новых записей.

### 5.6 Если сломалось

- **Бот молчит на `/start`** → polling не запустился. Логи: искать `Polling started`. Если нет — `BOT_TOKEN` неправильный.
- **`/admin_login` всегда «Неверный ключ»** → `BOT_ADMIN_ACCESS_KEY` пустой или не совпадает. Перепроверить через Railway → Variables (кликнуть глаз).
- **Бриф не пришёл в ADMIN_CHAT_ID** → бот не добавлен в чат, либо `ADMIN_CHAT_ID` ≠ реальному ID. Получить ID: добавить бота `@username_to_id_bot` в чат.
- **PDF не сгенерировался** → WeasyPrint упал. Логи: искать `WeasyPrintError`. Если шрифты — `fonts-dejavu` уже в Dockerfile, должно работать.

---

## 6. ШАГ 5. Аудит сайта (elephantdreams.ru)

### 6.1 Цель
Все страницы открываются, нет битых ссылок, аналитика работает, ссылки на бот ведут в @edl_os_bot.

### 6.2 Чек-лист страниц

Каждую страницу пройти в браузере + через `curl -I` (статус 200):

| URL | Что проверяем |
|---|---|
| `/` (index.html) | Hero, lead-magnet форма, CTA «Чекап» |
| `/audit.html` | Лендинг Чекапа (20 вопросов / 24ч / 9000₽) |
| `/pricing.html` | Лестница: Mini → Чекап → Стандарт → Премиум → Спринт |
| `/diagnostic.html` | Диагностика |
| `/sprint.html` | Спринт |
| `/cases.html` | Кейсы |
| `/faq.html` | FAQ (минимум 16 вопросов) |
| `/about.html` | Команда |
| `/methodology.html` | Методология |
| `/try-in-claude.html` | Гайд по работе в Claude |
| `/quiz.html` | Старый квиз (legacy, но рабочий) |
| `/legal/offer.html` | Оферта |
| `/legal/offer-checkup-2026-05.html` | Оферта Чекапа |
| `/legal/privacy.html` | Политика ПД |
| `/legal/terms.html` | Условия |
| `/404.html` | Кастомная 404 |

### 6.3 Автоматическая проверка

```bash
# 1. Все ссылки на сайте 200/3xx
for url in / /audit.html /pricing.html /diagnostic.html /sprint.html \
          /cases.html /faq.html /about.html /methodology.html \
          /try-in-claude.html /quiz.html \
          /legal/offer.html /legal/offer-checkup-2026-05.html \
          /legal/privacy.html /legal/terms.html /404.html ; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://elephantdreams.ru$url")
  echo "$code  $url"
done

# 2. Поиск битых исходящих ссылок в HTML
grep -rEho 'href="https?://[^"]+"' *.html | sort -u | \
  while read href; do
    url=$(echo "$href" | sed -E 's/.*"(https?:[^"]+)".*/\1/')
    code=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 10 "$url")
    [[ "$code" != "200" ]] && echo "$code  $url"
  done
```

### 6.4 UX-проверки (ручные)

- [ ] Mobile (DevTools → iPhone 14) — главная, audit, pricing, faq.
- [ ] CTA «Начать Чекап» на каждой странице ведёт на `tg://resolve?domain=edl_os_bot&start=...` или `https://t.me/edl_os_bot`.
- [ ] Telegram-кнопки имеют корректный `data-cta-type`, `data-cta-location` (для трекера).
- [ ] Открыть DevTools → Application → Local Storage → ключ `edl_events` должен наполняться при кликах.
- [ ] Если `window.EDL_ANALYTICS_ENDPOINT` определён — события уходят POST'ом (DevTools → Network → filter `analytics`).

### 6.5 SEO / гигиена

- [ ] Каждая страница имеет уникальный `<title>` и `<meta name="description">`.
- [ ] `<link rel="canonical">` присутствует.
- [ ] `og:image` отдаёт 200.
- [ ] `robots.txt` (если есть) не блокирует индексацию случайно.
- [ ] `sitemap.xml` (если есть) актуален.

### 6.6 Acceptance criteria

- [ ] Все страницы из 6.2 отдают 200.
- [ ] Битых исходящих ссылок 0 (или задокументировано исключение).
- [ ] Все CTA ведут на `@edl_os_bot`.
- [ ] Локальная аналитика наполняется.

---

## 7. ШАГ 6. Безопасность и приватность

### 7.1 Угрозы (см. `edl-os-bot/docs/threat_model.md`)

| Угроза | Защита (как должно быть) | Как проверить |
|---|---|---|
| Утечка ПД в LLM | `core/pd_sanitize.py` фильтрует email/телефон/ФИО перед отправкой | `pytest edl-os-bot/tests/test_pd_sanitize.py` |
| Off-topic в LLM | `core/scope_guard.py` whitelist/blacklist | `pytest edl-os-bot/tests/test_scope_guard.py` |
| Брутфорс `/admin_login` | Redis rate-limit: 3 попытки / 10 мин → блок 1 час | Шаг 5 ручная проверка: ввести неверный ключ 4 раза |
| Кража сессии админа | `AdminSession.expires_at`, проверка в `is_admin_active` | `SELECT * FROM admin_sessions WHERE expires_at < now()` — должны игнорироваться |
| SQL-инъекции | SQLAlchemy ORM, нет f-string в SQL | `grep -rn 'f".*SELECT\|f".*INSERT' edl-os-bot/src/` — должно быть пусто |
| Утечка секретов в логах | `BOT_TOKEN`, `ANTHROPIC_API_KEY` не должны логироваться | `grep -rn 'bot_token\|anthropic_api_key' edl-os-bot/src/ \| grep -i "log\|print"` |
| Telegram secret_token | При webhook — проверяется в `main.py:108` | Если используем webhook — заголовок обязателен |
| Открытый PG | DATABASE_URL должен быть internal | Шаг 3.4 |

### 7.2 Запустить тесты безопасности

```bash
cd edl-os-bot
pip install -e ".[dev]"
pytest tests/test_pd_sanitize.py tests/test_scope_guard.py tests/test_admin_auth.py tests/test_admin_session.py -v
```

### 7.3 Secret scan

Использовать GitHub MCP:
```
mcp__github__run_secret_scanning(owner="evzhiganova8888-hub", repo="edl-site")
```

### 7.4 Acceptance criteria

- [ ] Все security-тесты зелёные.
- [ ] Secret scan не нашёл закоммиченных секретов.
- [ ] `.env*` в `.gitignore` (проверить: `grep -E '^\.env' .gitignore`).
- [ ] В `events` нет записей с сырыми email/телефонами в `payload`.

---

## 8. ШАГ 7. Полный QA-прогон (по типам тестов)

### 8.1 Unit + integration (pytest)

```bash
cd edl-os-bot
pytest -v --tb=short --maxfail=10
```

**Ожидание**: 0 failed, 0 errors. Если есть failed после merge PR #18 — открыть `docs/qa_pr18_smoke_results.md` для контекста.

### 8.2 Regression (adversarial / sycophancy / scope)

```bash
cd edl-os-bot
pip install -r tests/requirements-regression.txt
bash tests/regression.sh        # старый формат
python tests/run_regression_v3_1.py  # новый формат
```

Сверить с baseline `tests/regression_v3_1_last_report.json`. Любая регрессия (раньше pass → теперь fail) — **блокер для релиза**.

### 8.3 Functional (по checkup-content)

Открыть `docs/qa_pr18_checkup_content_findings.md`, пройти каждый «finding» руками в боте.

### 8.4 Перформанс (smoke)

- `/start` → ответ ≤ 2 сек.
- `/audit` → шаг FSM → ответ ≤ 3 сек.
- `/checkup` ответ на вопрос (с LLM-валидацией качества) → ≤ 10 сек.
- `/applications pending 5` → ≤ 3 сек (зависит от размера таблицы).

Если LLM-ответы > 15 сек — проверить `ANTHROPIC_BASE_URL` (proxyapi.ru может быть медленный).

### 8.5 Локализация / контент

- [ ] Все строки в боте — на русском (нет «Hello» / «Sorry»).
- [ ] Кавычки — `«ёлочки»`, а не `"прямые"` (где уместно).
- [ ] Эмодзи — умеренно (см. brand guide в `BOT_TZ_v3.md`).
- [ ] Тон — «вы», деловой, без излишней эмоциональности.

### 8.6 Acceptance criteria

- [ ] pytest: 100% pass.
- [ ] Regression: нет регрессий vs baseline.
- [ ] Все findings из QA-доков либо исправлены, либо документированы как «accept».
- [ ] Перформанс в SLA.

---

## 9. ШАГ 8. Наблюдаемость и логирование

### 9.1 Что должно быть в логах Railway

При старте:
```
[INFO] src.main: Polling started
[INFO] src.main: (если webhook) Webhook set to https://...
```

При работе:
```
[INFO] httpx: HTTP Request: POST .../getUpdates "HTTP/1.1 200 OK"  # каждые 10 сек
```

При ошибках:
```
[ERROR] src.bot.handlers: ... (stack trace)
```

### 9.2 Чего быть не должно

- `[WARNING] BOT_TOKEN is not set`
- `[ERROR] asyncpg.exceptions.ConnectionDoesNotExistError`
- `[ERROR] redis.exceptions.ConnectionError`
- Любой `Traceback (most recent call last)` без последующего `handled`.

### 9.3 Метрики (если есть Railway → Metrics)

- CPU: < 50% в среднем (бот сидит на polling — низкая нагрузка).
- Memory: < 400 МБ (Python + WeasyPrint + cached LLM).
- Network egress: zigzag (polling каждые 10 сек).

### 9.4 Бот-ошибки в БД

```sql
SELECT created_at, error_type, message FROM bot_errors
ORDER BY created_at DESC LIMIT 20;
```

Если новые ошибки за последний час после деплоя — диагностика.

### 9.5 Acceptance criteria

- [ ] В логах есть `Polling started`.
- [ ] Нет ERROR-уровня за последние 30 минут.
- [ ] `bot_errors` не растёт.

---

## 10. ШАГ 9. Документация и финализация

### 10.1 Обновить README

`edl-os-bot/README.md` — раздел Deploy:
- Шаги настройки Railway.
- Полный список env vars (можно ссылкой на этот ТЗ).
- Как добавить нового админа (вставить tg_id в `ADMIN_USER_IDS`).
- Как сгенерировать `BOT_ADMIN_ACCESS_KEY`.

### 10.2 Обновить `.env.example`

Создать/обновить `edl-os-bot/.env.example` со ВСЕМИ переменными из раздела 3.2 (значения — плейсхолдеры).

### 10.3 Создать `docs/runbook.md`

Краткий runbook на типовые проблемы:
- Бот не отвечает → шаги диагностики.
- Healthcheck падает → шаги.
- /admin_login не работает → шаги.
- Оплата не приходит → шаги (для будущего, когда YooKassa активен).

### 10.4 Создать `docs/release_checklist.md`

Чек-лист перед каждым релизом:
- [ ] pytest зелёный.
- [ ] regression без регрессий.
- [ ] Миграции включены в PR.
- [ ] `.env.example` обновлён, если добавили новые vars.
- [ ] Smoke-test после деплоя.

### 10.5 Acceptance criteria

- [ ] README актуален.
- [ ] `.env.example` есть, переменные совпадают с config.py.
- [ ] Runbook + release checklist есть.

---

## 11. ШАГ 10. Финальный отчёт

В конце всей работы — отчёт в Markdown с:

1. **Что сделано** (галочки по всем acceptance criteria).
2. **Что не сделано и почему** (если что-то осталось — явно).
3. **Оценка состояния** по разделам (1-10):
   - Деплой: __/10
   - Переменные: __/10
   - Миграции: __/10
   - Smoke-тест: __/10
   - Сайт: __/10
   - Безопасность: __/10
   - QA: __/10
   - Наблюдаемость: __/10
   - Документация: __/10
   - **Общая**: __/10
4. **Топ-5 рисков** на ближайший месяц.
5. **Рекомендации** (что делать дальше — переезд на webhook, YooKassa, и т.д.).

---

## 12. ПРИЛОЖЕНИЕ A. Полезные команды

### 12.1 Локальный запуск бота

```bash
cd edl-os-bot
cp .env.example .env  # заполнить ключи
docker compose up postgres redis -d
alembic upgrade head
python -m src.main
```

### 12.2 Подключение к Railway Postgres локально

```bash
# Public URL из Railway → Postgres → Connect
psql "postgresql://postgres:PASSWORD@HOST.railway.app:PORT/railway"
```

### 12.3 Telegram bot debug

```python
# В Python REPL:
import asyncio
from telegram import Bot
b = Bot("YOUR_BOT_TOKEN")
asyncio.run(b.get_me())  # должен вернуть info
asyncio.run(b.get_webhook_info())  # проверить webhook (если используется)
```

### 12.4 Force-redeploy на Railway (без push)

UI: edl-site → Deployments → последний → ⋮ → **Redeploy**.

---

## 13. ПРИЛОЖЕНИЕ B. Когда что-то идёт не по плану

### Принципы

1. **Не делать destructive операций** (`DROP TABLE`, `git push --force`, `rm -rf`) без явного подтверждения пользователя.
2. **Root cause > быстрый фикс**. Если падает healthcheck — диагностировать причину, а не отключать healthcheck.
3. **Откат через revert, а не через force-push**: `git revert <commit>` + новый PR.
4. **Backup перед миграциями**: Railway → Postgres → Backups → Create backup.

### Эскалация

Если после 3 попыток исправления одна и та же проблема не решена — остановиться, написать отчёт «что попробовали, что не сработало, гипотезы», запросить помощь пользователя.

---

## 14. ПРИЛОЖЕНИЕ C. Ссылки

- **Репо**: https://github.com/evzhiganova8888-hub/edl-site
- **Сайт**: https://elephantdreams.ru
- **Бот**: https://t.me/edl_os_bot
- **Канал**: https://t.me/edl_os
- **Railway**: https://railway.com/project/cb1e0a98-e75f-47b9-90e7-78c27bf6d4b8
- **Railway docs**: https://docs.railway.com/
- **python-telegram-bot docs**: https://docs.python-telegram-bot.org/
- **YooKassa API**: https://yookassa.ru/developers
- **WeasyPrint**: https://doc.courtbouillon.org/weasyprint/
- **Anthropic API**: https://docs.anthropic.com/

---

## 15. ЧТО НАПИСАТЬ В НОВОМ ЧАТЕ

Скопировать пользователю для старта нового чата с Sonnet:

```
Прочитай ТЗ: /Users/apple/edl-site/docs/AUDIT_TZ_v1_for_sonnet.md

Текущий блокер: новые деплои Railway падают на Healthcheck (uvicorn слушает
hardcoded port=8000, а Railway инжектит $PORT). Начни с раздела 2 (Шаг 1).

После каждого шага — отчитайся коротко, дождись подтверждения, потом следующий.
Без явного "ok, продолжай" не мерджи PR в main.
```

---

_Конец ТЗ v1.0. Если по ходу работы выяснилось что-то новое — обновить ТЗ через PR._
