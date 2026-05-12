# EDL OS Bot — История сессии (11–12 мая 2026)

## Финальный статус: ✅ Бот работает
- **Хостинг:** Railway, проект `efficient-appreciation`, environment `production`, EU West (Amsterdam)
- **Сервисы:** edl-site (бот, Online), Postgres (Online), Redis (Online)
- **Telegram:** [@edl_os_bot](https://t.me/edl_os_bot) — отвечает на `/start`
- **Сайт:** https://elephantdreams.ru — все 8 CTA ведут в бота с правильными `?start=` параметрами

## Что сделано на GitHub (main ветка)

| Коммит | Что |
|---|---|
| `33c96ec` | Этап 1: каркас + БД + handlers + промпты + тесты (+3560 строк) |
| `13a8fc6` | Этап 2: Robokassa + оплата Чекапа + 14-дневный возврат + hand-off + стикеры (+1752) |
| `317ac87` | Этап 3: Quiz + FAQ + админка + регрессия 18 (+1408) |
| `0bc0e8f` | Сайт→бот deep-links + PROGRESS.md (+190) |
| `bbe2643` | Merge PR #1 в main |

Итого: 126 файлов, ~6720 строк. Полный MVP по `BOT_TZ_v3.md`.

## Конфигурация Railway (на edl-site service)

**Settings → Source:**
- Repo: `evzhiganova8888-hub/edl-site`
- Branch: `main`, auto-deploys: ON
- Root Directory: `/edl-os-bot`

**Settings → Build:**
- Builder: Dockerfile (auto-detected)

**Settings → Deploy:**
- Custom Start Command: `sh -c "alembic upgrade head && python -m src.main"`

**Variables (24 шт):**
- `BOT_TOKEN=<свежий из BotFather, в чате не светить>`
- `ANTHROPIC_API_KEY=<пусто — потом>`
- `ADMIN_USER_IDS=265061355`
- `ADMIN_CHAT_ID=-1003928057893`
- `DATABASE_URL=postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}`
- `SYNC_DATABASE_URL=postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}`
- `REDIS_URL=${{Redis.REDIS_URL}}`
- `ENVIRONMENT=production`
- `VITACONSULT_PUBLIC=false`
- `SALES_USERNAME=lvanKhudyakov`
- `CHANNEL_URL=https://t.me/edl_os`
- `SITE_URL=https://elephantdreams.ru`
- `PRIVACY_POLICY_URL=https://elephantdreams.ru/legal/privacy.html`
- `OFFER_URL=https://elephantdreams.ru/legal/offer.html`
- `PRIVACY_POLICY_VERSION=2026-05-11`
- `WORKING_HOURS_START=10`
- `WORKING_HOURS_END=19`
- `TIMEZONE=Europe/Moscow`
- `ROBOKASSA_IS_TEST=1`
- `ROBOKASSA_MERCHANT_LOGIN=<пусто>`
- `ROBOKASSA_PASSWORD_1=<пусто>`
- `ROBOKASSA_PASSWORD_2=<пусто>`
- `ANTHROPIC_MODEL=claude-haiku-4-5-20251001`
- `ANTHROPIC_MAX_TOKENS=1024`

## Проблемы которые решили

1. Docker Desktop не ставится на macOS 13.7 → перешли на Railway
2. Railway не находит репо → Configure GitHub App → выбрать edl-site → Save
3. Build vs Start Command конфликт → `buildCommand` очистить, оставить только `startCommand`
4. `psycopg2` не установлен → `SYNC_DATABASE_URL` префикс `postgresql+psycopg://` (вместо `postgresql://`)
5. Контейнер завершается после миграций → Custom Start Command обернуть в `sh -c "..."` чтобы `&&` сработал

## Что осталось (по приоритету)

### Безопасность (сделать прямо сейчас)
- ⚠️ Revoke BOT_TOKEN в BotFather → новый в Railway Variables → Deploy
- ⚠️ Revoke GitHub PAT — на странице github.com/settings/personal-access-tokens

### До запуска оплат (Спринт 2 blockers)
- Юр-консультация (оферта + ревью 152-ФЗ) — 5–10к ₽, 3–5 дней
- Аккредитация Robokassa у ИП Жигановой — 3–5 дней
- Текст оферты на `elephantdreams.ru/legal/offer.html`
- Заполнить `ROBOKASSA_*` переменные в Railway

### Артефакты `/audit_sample`
- Обезличенный PDF отчёта Чекапа → `edl-os-bot/assets/audit_sample.pdf`
- То же в HTML → `assets/audit_sample.html`
- 1-минутное видео-разбор Кати → `assets/audit_sample_video.mp4`

### Для свободного диалога через AI
- Anthropic API key ($30 на тест) → `ANTHROPIC_API_KEY` в Railway → Deploy

### Перед публичным запуском
- 3 живых респондента из КСДВ (manufacturing/services_legal/marketplace_accounting)
- Прогон `python tests/run_regression.py` через настоящий Claude → цель 16/18 PASS

### После защиты #2 (22.05)
- В Telegram боте `/admin` → кнопка «Включить VITACONSULT» — имя клиента можно будет упоминать в кейсе

## Ключевые ссылки

- Репо: https://github.com/evzhiganova8888-hub/edl-site
- ТЗ: https://github.com/evzhiganova8888-hub/edl-site/blob/main/BOT_TZ_v3.md
- Прогресс: https://github.com/evzhiganova8888-hub/edl-site/blob/main/PROGRESS.md
- Railway проект: railway.com → workspace evzhiganova8888-hub → project efficient-appreciation
- Bot: https://t.me/edl_os_bot
- Sales-чат (-1003928057893): «Отдел продаж Elephant Dreams | KENA»

## Команды бота для теста

- `/start` — главное меню
- `/start quiz` — Founder OS Score (12 вопросов)
- `/start demo` / `/start audit` / `/start diagnostic` / `/start sprint_waitlist` — deep-link сценарии
- `/audit_sample` — пример отчёта (когда положишь PDF)
- `/faq` — 11 вопросов
- `/privacy` — твои данные (152-ФЗ)
- `/refund` — возврат (14 дней)
- `/admin` — сводка + toggle (только для тебя по telegram_id `265061355`)
- `/reset` — сбросить контекст диалога

## Как продолжить завтра

В новой сессии Claude напиши:

> Продолжаем работу над EDL OS Bot. Репо `evzhiganova8888-hub/edl-site`, ветка `main`. Бот развёрнут на Railway. Файлы для контекста: `BOT_TZ_v3.md`, `PROGRESS.md`, `SESSION_HISTORY.md`. Нужно [твоя задача].

Прикрепи этот файл — Claude подхватит всё.
