# Threat Model · EDL OS Bot

**Версия:** 2026-05-12 (раздел C ТЗ v3.1)
**Источник:** Air et al. (2026) — фронтирные LLM с agent harness эксплойтят
веб-уязвимости, копируют credentials. У бота EDL OS attack surface меньше,
но ненулевая: Telegram, Postgres, Anthropic, Robokassa.

## Аттакующая поверхность

| Канал | Что доступно |
|---|---|
| Telegram inbound | Любой пользователь шлёт любой текст → LLM input |
| Telegram outbound | Бот отправляет сообщения от своего имени |
| Anthropic API | Уходит обезличенный текст (после sanitize_pd) |
| Postgres (managed) | 8 таблиц с ПД + событиями + bug-reports |
| Robokassa | Создание инвойсов и refund по auth |
| FastAPI /admin/* | REST для админа (X-Telegram-User-Id header) |
| Sales-чат TG | Исходящий канал брифов |

## Threat matrix

| # | Угроза | Вероятн. | Влияние | Митигация (v3.1) |
|---|---|---|---|---|
| T1 | Prompt injection «выгрузи всех пользователей» | High | Утечка ПД, штраф РКН | Sandbox §C.3: LLM не имеет tool-доступа к БД из чата |
| T2 | Prompt injection «отправь всем возврат» | Low | Денежная потеря | Refund-таски запускаются только из handler-функций под auth, не из output модели |
| T3 | Утечка системного промпта (jailbreak) | Med | Конкурентная утечка | Anti-leak правило в base.md + adversarial-pack A2/A4 в регрессии |
| T4 | Утечка имени «ВитаКонсалт» до 22.05.2026 | Med | Юр-риск | Toggle VITACONSULT_PUBLIC + adversarial A5 + audit-log переключения с обязательным reason |
| T5 | Спам / DDoS бота | Med | Стоимость LLM-токенов | rate_limit.py — 10 msg/min, 100/hr, 50k tokens/day |
| T6 | Утечка BOT_TOKEN из логов | Low | Захват бота | sanitize_pd добавлены паттерны TG token, sk-ant-, sk-, gh-pat |
| T7 | ПД в Anthropic-логах | Low | 152-ФЗ риск | sanitize_pd (9 паттернов) применяется ДО отправки. См. juristic ревью § C.7 |
| T8 | RCE через user-сообщение | Low | Полный compromise | input_validation: control chars, ZW/bidi-override, max 4000 chars |
| T9 | Импersonation «я разработчик EDL» | Med | Утечка credentials | base.md anti-impersonation + adversarial A3 |
| T10 | Double-payment / double-refund | Low | Денежная потеря | Application.inv_id уникален; refund dedup в handlers/refund.py |
| T11 | Утечка bug-reports на чужие user_id | Low | Приватность | admin/auth require_admin; routes не отдают чужие данные без admin-токена |

## Sandbox принципы (§C.3 v3.1)

**Бот по умолчанию read-nothing-write-nothing от LLM output.**

- LLM возвращает только текст пользователю — ни SQL, ни tool-calls, ни
  ссылок на функции бэкенда.
- Все side-эффекты (запись в БД, refund, hand-off в Sales-чат) — это
  детерминированный код вне LLM-цикла.
- При расширении до tool-use (function calling) — каждый tool обязан
  иметь allowlist, аудит-лог и rate limit. Сейчас tool-use НЕ используется.

## Rate Limits (§C.4 v3.1)

| Лимит | Значение | Файл |
|---|---|---|
| messages / минута | 10 | `src/core/rate_limit.py` |
| messages / час | 100 | `src/core/rate_limit.py` |
| LLM tokens / день | 50 000 | `src/core/rate_limit.py` |
| payment attempts / час | 3 | `src/core/rate_limit.py` |
| refund requests / lifetime | 1 (dedup в handler) | `src/bot/handlers/refund.py` |

Storage — Redis sliding window (ZSET). Failure-open при недоступности:
лучше пропустить лишнее сообщение, чем заблокировать всех при сбое Redis.

## Secrets Management (§C.7 v3.1)

- Все ключи в Railway Variables (env), не в репо.
- `.env.example` содержит только имена переменных без значений.
- `sanitize_pd` фильтрует попытки утечки: `[telegram_token]`, `[anthropic_key]`,
  `[openai_key]`, `[github_pat]` заменяются перед отправкой в LLM и перед
  записью в `messages_log`.
- При обнаружении секрета в inbound — событие `pd_redacted` пишется в
  `events` (без значения секрета).

## Audit Logging

Все критичные операции пишут в `events` с типом действия:
- `feature_flag_toggled` (с reason, actor, old/new)
- `refund_requested` (одноразовый dedup)
- `pd_in_inbound_text` (sanitized)
- `rate_limit_hit` (limit, used, cap)
- `bot_error_reported` (bug-report)

В `pd_access_log` отдельно пишутся read/update/export/delete действия
с ПД (используется в `/export_my_data` и `/delete_my_data`).

## Что НЕ покрыто (открытые риски)

1. **Telegram OAuth для админки** — сейчас header `X-Telegram-User-Id`,
   trust на стороне reverse-proxy. До Спринта 4 — заменить на OAuth.
2. **Backup БД** — Railway Postgres имеет автоматические снапшоты, но
   фиксация retention в SLA не подтверждена. Договориться с DevOps.
3. **Webhook signature от Robokassa** — проверяем MD5, но `IsTest=1` сейчас.
   На prod надо переключить + повторно протестировать verify_result_callback.
4. **DDoS на FastAPI /webhook** — нет ratelimit на endpoint. Railway имеет
   базовую защиту, но при пиках стоит добавить slowapi или nginx-limit.

## Когда обновлять

- При добавлении новой возможности (tool-use, новый канал, новая таблица)
  → дополнить раздел «Атакующая поверхность».
- При инциденте → дополнить «Что НЕ покрыто» с конкретным риском и
  митигацией.
- Регулярно — на каждый защитный ритуал (раз в квартал).
