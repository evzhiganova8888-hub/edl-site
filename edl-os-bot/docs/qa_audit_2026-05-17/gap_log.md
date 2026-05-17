# Gap log — несоответствия ТЗ ↔ реализация

> Сессия: smoke по 22 commands + 19 callback patterns.
> Полный аудит §6–§9 ТЗ v3.1 — отложен. Здесь только то, что бросилось в глаза.

---

## §1.5 ТЗ (правила First Action)

Соблюдены:
- ✅ Stack trace получен (Railway logs до правок).
- ✅ Ветка `claude/qa-audit-2026-05-17` от main.
- ✅ Каждый крупный шаг отчитан, ждём «ok».
- ✅ Ничего не пушится в main без явного подтверждения.

---

## §5.3 Принципы — кросс-проверка

| Принцип | Реализация | Статус |
|---------|------------|--------|
| 1. Реальные данные, не моки | conftest подменяет DB на SQLite — но это для unit-тестов, прод использует Postgres | ✅ |
| 2. Stage cold→warm→hot | `User.stage` и `User.segment` есть в моделях | ✅ |
| 3. Single source of truth для PD | `User` model + `pd_sanitize.py` | ✅ |
| 4. Calendar-based offers | `working_hours.is_working_now()` + RF_HOLIDAYS до 2027 | ✅ |
| 5. Idempotent webhooks | `/webhook` endpoint парсит updates; deduplication на уровне Telegram offset | ⚠️ только в polling; в webhook режиме нет explicit dedup |
| 6. Manual escalation as fallback | `hand-off` → @lvanKhudyakov в любой непонятной ситуации | ✅ |
| 7. Audit trail в events table | `log_event(...)` вызывается в большинстве сценариев | ✅ |
| 8. Уведомления Ивану не зависят от ответа юзеру | Брифы в `send_to_admin_chat` отдельным вызовом | ✅ |

---

## §6 — функциональный охват (smoke-уровень)

| Команда | Зарегистрирована | Smoke OK | Полный flow проверен |
|---------|------------------|----------|-----------------------|
| `/start` | ✅ | ✅ | частично (3 из 7 deep-links) |
| `/help` | ✅ | ✅ | ✅ |
| `/menu` | ✅ | ✅ | ✅ |
| `/faq` | ✅ | ✅ | ❌ (нет тестов на конкретные FAQ items) |
| `/privacy` | ✅ | ✅ | ❌ |
| `/delete_my_data` | ✅ | ✅ (есть в `test_consent.py`) | ❌ (full lifecycle) |
| `/export_my_data` | ✅ | ✅ | ❌ |
| `/audit` | ✅ | ✅ | ❌ (FSM lead-capture не end-to-end) |
| `/audit_sample` | ✅ | ✅ | ❌ |
| `/refund` | ✅ | ✅ | ❌ (14-day window edge cases) |
| `/quiz` | ✅ | ✅ (есть в `test_quiz.py`) | ✅ |
| `/admin` | ✅ | ✅ | ❌ (8 sub-commands не покрыты) |
| `/admin_login` | ✅ | ✅ (есть в `test_admin_auth.py`) | ✅ |
| `/admin_logout` | ✅ | ✅ | ✅ |
| `/mark_paid` | ✅ | ✅ | ❌ (только happy path) |
| `/applications` | ✅ | ✅ | ❌ |
| `/emails_dump` | ✅ | ✅ | ❌ |
| `/beta_summary` | ✅ | ✅ | ❌ |
| `/checkup` | ✅ | ✅ | ❌ (FSM 20 вопросов end-to-end не тестируется) |
| `/bugs` | ✅ | ✅ | ❌ |
| `/feedback` | ✅ | ✅ | ❌ |
| `/reset` | ✅ | ✅ | ✅ |

**Покрытие full flow: ~5 из 22 команд = ~23%.**

---

## §7 — негативные кейсы (не покрыты в этой сессии)

- Длинный текст (> 4096 символов) → Telegram отклонит. Не тестируется.
- Спам однотипными командами (5/сек) → rate-limit. Есть в `admin_login`, нет глобально.
- Эмодзи / UTF-8 / RTL → `pd_sanitize` обрабатывает, но edge cases не тестируются.
- Слом FSM посередине (выслать `/audit` → бросить → послать `/start` → попытаться продолжить) → `/reset` нужен, но не очевидно для юзера.
- Параллельная отправка от одного юзера → ConcurrentModificationError на User row? Не проверено.

---

## §8 — безопасность (spot-check)

| Категория | Что есть | Что отсутствует |
|-----------|----------|-----------------|
| Admin auth | `is_admin()` + `/admin_login` с rate-limit | Нет TOTP / MFA |
| SQL injection | SQLAlchemy parametrized queries | Нет prepared statements review |
| XSS в bug-report | `validate_user_text` (есть в `input_validation.py`) | Не тестируется на конкретные XSS payloads |
| PD leakage в LLM | `pd_sanitize.py` маскирует email/phone | Не покрыты case-insensitive variants |
| Webhook secret | `WEBHOOK_SECRET_TOKEN` сравнивается в `main.py:104–108` | После активации webhook — это в проде защищает |
| Rate limit | Только на `/admin_login` (Redis) | Нет на `/audit`, `/quiz`, free-text dialog |
| 152-ФЗ согласие | `consent.py` модуль есть, `consent_log` table | Не проверено, что согласие requested до сохранения PD |

---

## §10 — Vitaconsult toggle (бизнес-флаг)

- `VITACONSULT_PUBLIC=false` в config — корректно (NDA до 22.05.2026).
- После 22.05.2026 — переключить через Railway Variables. Поведение код-side не проверялось в этой сессии.

---

## §12 — Hand-off rules

- `src/core/handoff.py:get_rule(segment)` — централизованная маршрутизация по сегменту.
- SLA: in-hours / out-of-hours формулировки в `notifications.py` (`humanize_window`).
- Бриф Ивану — `build_lead_brief()` структурирован по §12.3.
- ✅ Хорошее покрытие на уровне кода. Юнит-тесты есть (`test_handoff.py`, `test_notifications.py`).

---

## Главные gap'ы для следующих итераций

1. **Тестирование PDF generation** — WeasyPrint не покрыт pytest. Невозможно проверить регрессию без Docker сборки.
2. **End-to-end FSM** — для `/audit`, `/checkup`, `/refund` нет тестов, которые проходят полный flow с реальной БД.
3. **Concurrent user load** — не проверена поведение при 10/100/1000 одновременных юзеров.
4. **Полный negative test pack** — §7 ТЗ описывает ~30 негативных кейсов, покрыто <10%.
5. **Security audit** — `threat_model.md` есть в docs/, но full penetration test не делался.
