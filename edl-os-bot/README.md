# EDL OS Bot · @edl_os_bot

Telegram-бот EDL OS. Канонический документ — `../BOT_TZ_v3.md`.

## Что это

Единая входная точка с сайта elephantdreams.ru и из канала @edl_os.
Принимает 7 типов deep-link, квалифицирует по 8+1 сегменту, ведёт диалог
на RAG поверх публичных доков EDL, принимает оплату 9 000 ₽ за
Бизнес-чекап (Robokassa), передаёт квалифицированных лидов Ивану.

## Стек

- Python 3.12, FastAPI, python-telegram-bot 21+
- PostgreSQL 16 (managed Selectel)
- SQLAlchemy 2 + Alembic
- Redis + Celery
- Anthropic Claude Haiku 4.5

## Быстрый старт (локально)

```bash
# 1. Скопировать env
cp .env.example .env
# Заполнить BOT_TOKEN, ANTHROPIC_API_KEY

# 2. Поднять Postgres + Redis + бот
docker compose up -d postgres redis
docker compose run --rm bot alembic upgrade head
docker compose up bot

# Или локально без Docker:
pip install -e .
alembic upgrade head
python -m src.main
```

## Релизные этапы

- **Этап 1 (Спринт 1):** скелет, БД, главное меню, 7 deep-link заглушек,
  согласие на ПД, BASE-промпт LLM. *(текущий)*
- **Этап 2 (Спринт 2):** Robokassa, оплата Чекапа, возвраты, hand-off,
  out-of-hours, стикеры, /privacy.
- **Этап 3 (Спринт 3):** Quiz, Diagnostic, Sprint waitlist, FAQ, админка,
  метрики, регрессия 16/18.

## Структура

См. `BOT_TZ_v3.md` §15 и `../BOT_TZ.md` v1 для исторического контекста.

```
edl-os-bot/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── alembic/versions/      # миграции БД
├── src/
│   ├── main.py            # FastAPI app + bot bootstrap
│   ├── bot/handlers/      # /start, /audit, /privacy и т.д.
│   ├── core/              # segment, consent, llm, payments, working_hours
│   ├── prompts/           # BASE + verticals + stages + handoff
│   ├── knowledge_base/    # RAG-доки
│   ├── db/                # SQLAlchemy models + repos
│   ├── admin/             # FastAPI admin app
│   ├── tasks/             # Celery (14-дневный refund check, рассылки)
│   └── utils/
├── assets/                # audit_sample.pdf/html/mp4, offer.pdf
└── tests/                 # regression_v3.json + pytest
```

## Юр-compliance

ПД хранятся только в РФ (Selectel/Yandex Cloud). LLM (Anthropic) получает
только обезличенный текст через `core/pd_sanitize.py`. 152-ФЗ согласие
обязательно перед сбором любых ПД. Подробнее — `BOT_TZ_v3.md` §9.
