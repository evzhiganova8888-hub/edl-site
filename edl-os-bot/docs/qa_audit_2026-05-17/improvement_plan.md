# Improvement plan — после QA audit 2026-05-17

> Что НЕ сделано в этом PR, но должно быть сделано в следующих итерациях.

---

## Спринт 1 (сразу после мерджа этого PR)

### 1. Активировать webhook на Railway (вручную, Евгения)

**Время**: 5 минут. **Блокер**: P0-1 «menu + error».

См. [RAILWAY_WEBHOOK_SETUP.md](RAILWAY_WEBHOOK_SETUP.md). Выставить 2 env vars:
- `WEBHOOK_BASE_URL=https://edl-site-production.up.railway.app`
- `WEBHOOK_SECRET_TOKEN=<32 рандомных символа>`

После — проверить Railway logs на `Starting in WEBHOOK mode` и попробовать `/start` от своего аккаунта.

### 2. Прод-верификация: послать /start от 3 разных аккаунтов

Через 24 часа после активации webhook. Цель: убедиться, что в `events` table нет новых записей с `event='unhandled_exception'` и нет повторных «menu + error» сообщений.

SQL для проверки:
```sql
SELECT occurred_at, payload->>'tb_tail'
FROM events
WHERE event='unhandled_exception'
  AND occurred_at > '2026-05-17 21:00:00+03'
ORDER BY occurred_at DESC LIMIT 20;
```

Если за 24 часа 0 записей — P0 закрыт.

---

## Спринт 2 (1–2 недели)

### 3. yookassa idempotency перед активацией

**Файл**: [audit.py:507–517](../../src/bot/handlers/audit.py#L507).

Перед `session.add(Payment(...))` добавить:
```python
existing = await session.scalar(
    select(Payment).where(Payment.provider_invoice_id == str(app.inv_id))
)
if existing:
    return existing  # вернуть существующий, не создавать дубль
```

Регрешн-тест: двойной клик на «Оплатить» создаёт ровно одну строку Payment.

**Приоритет**: P1, делать до активации `PAYMENT_MODE=yookassa`.

### 4. FSM state cleanup

**Файлы**: `audit.py:328`, `checkup.py` (после `_finalize_checkup`).

Добавить utility `_clear_fsm_state(context, keys)` и вызывать в конце каждого FSM-сценария. Регрешн: после прохождения flow `context.user_data` пуст.

**Приоритет**: P2.

### 5. Дубль event log в /mark_paid

**Файл**: [admin.py:214–224](../../src/bot/handlers/admin.py#L214). Проверить `result.get("already_paid")` до `log_event`.

**Приоритет**: P2.

---

## Спринт 3 (3–4 недели)

### 6. Полный QA audit §6–§9 ТЗ (Опция C)

То, что было отложено в этой сессии. Объём: ~110 функциональных кейсов + ~30 негативных + security checklist. Время: 5–8 часов.

Деление на 4 параллельных под-аудита:
- §6.1–§6.6 — public commands + lead capture
- §6.7–§6.18 — checkup / admin / privacy / refund
- §7 — все негативные кейсы (lengths, rate, FSM breaking)
- §8 + §9 — security + perf

Каждый — отдельный PR с регрешн-тестами.

### 7. End-to-end FSM тесты с реальной БД

Сейчас тесты используют SQLite in-memory. Это OK для unit, но FSM не тестируется end-to-end (`/audit` → lead capture → payment → checkup).

План: pytest-fixture с testcontainers Postgres + Redis, отдельный `tests/e2e/` directory, маркер `@pytest.mark.e2e` (не запускается в CI по умолчанию, только pre-release).

### 8. PDF generation regression

WeasyPrint не покрыт в pytest. План: интеграционный тест в Docker container, который генерирует PDF из тестового checkup и проверяет, что файл > 10KB и парсится PyPDF2 без ошибок.

---

## Долгосрочно (после релиза)

### 9. Перейти на ConversationHandler для FSM

Сейчас FSM реализован вручную через `context.user_data` ключи. Это работает, но:
- легко забыть очистить state
- нет автоматического timeout
- сложно тестировать

PTB `ConversationHandler` решает всё это. Миграция большая (нужно переписать `audit.py` и `checkup.py`), но окупится в долгую.

### 10. Observability: метрики и алерты

Сейчас всё в `events` table — это OK для аудита, но не для real-time. Предложение:
- Sentry SDK для unhandled_exception (auto-alert в Slack)
- Prometheus exporter для FastAPI: latency `/webhook`, error rate, count активных FSM-сессий
- Grafana dashboard с алертами при > 5 errors / 5 min

### 11. CI: гарантия что pytest проходит на каждом PR

Сейчас неясно, есть ли CI hook. Если нет — добавить GitHub Action `.github/workflows/tests.yml`:
```yaml
on: [pull_request]
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt -r tests/requirements-regression.txt
      - run: pytest -q
```

### 12. ConversationHandler timeout / `/cancel` глобально

Если юзер начал `/audit`, FSM-state в user_data может висеть месяцами. Решение:
- timeout 30 минут (после `/audit` ничего не отвечает — FSM сбрасывается, юзер получает `/menu`)
- глобальный `/cancel` (явный сброс из любого state)

---

## Что НЕ делать

- ❌ **Не активировать `PAYMENT_MODE=yookassa` без п.3 (idempotency).**
- ❌ Не пушить никакие фичи в main без хотя бы smoke pytest.
- ❌ Не убирать `_global_error_handler` — это последняя линия защиты юзера.
- ❌ Не убирать `_safe_uuid` — даже если callback_data всегда генерится нами, регрессия в keyboards.py может сломать prod.
