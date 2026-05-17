# ТЗ: Полный QA-аудит Telegram-бота EDL OS (@edl_os_bot)

> **Адресат**: Claude Sonnet 4.6 (новый чат Claude Code, web/desktop).
> **Автор ТЗ**: Tech Lead + Senior QA (15+ лет B2B SaaS, 5+ лет Telegram-боты).
> **Дата**: 2026-05-17.
> **Версия ТЗ**: v1.0.
> **Предыдущая работа**: PR #21 (PORT-фикс деплоя), PR #22 (.env.example + runbook + release_checklist).

---

## 0. КАК ЧИТАТЬ ЭТО ТЗ

1. Прочитай **§1 (Критичный баг с прода)** и **§2 (Цели аудита)** — это контекст.
2. Прочитай **§3 (Источники правды)** — где спецификации продукта.
3. Дальше — по шагам **§4 → §13**, не пропуская.
4. После каждого крупного шага — отчёт пользователю (Евгения), пауза для подтверждения.
5. **Не пушить ничего в `main` без явного «ok»** от пользователя.
6. Все правки кода — через ветку `claude/qa-audit-<auto-suffix>`, draft PR.

**Базовый принцип**: «5+ лет QA для B2B Telegram-ботов» = ты не доверяешь предположениям. Сначала **репродукция + извлечение реального стек-трейса**, потом гипотеза, потом фикс, потом регрессионный тест на этот случай.

---

## 1. КРИТИЧНЫЙ БАГ С ПРОДА (репродуцирован визуально 17.05.2026 17:26 МСК)

### 1.1 Симптомы

При отправке `/start` или `/menu` в `@edl_os_bot` пользователь получает **одновременно** (с разницей <1 сек):
- Главное меню с кнопками («Что дальше?» + 11 кнопок).
- Сообщение:
  > Что-то пошло не так на нашей стороне. Я уже сообщил команде.
  > Если срочно — напишите Ивану: @lvanKhudyakov.
  > Чтобы вернуться в меню: /menu

### 1.2 Источник fallback-сообщения

Файл: `edl-os-bot/src/bot/handlers/__init__.py:60-64` — функция `_global_error_handler()`. Это глобальный error handler, ловит **любой** неперехваченный exception и:
1. Логирует traceback в `logger.error` (Railway logs).
2. Отвечает пользователю fallback-сообщением.
3. Пишет в таблицу `events` запись с `event='unhandled_exception'`, payload содержит `tb_tail` (последние 1500 символов стек-трейса).

### 1.3 Корневая причина — НЕИЗВЕСТНА

Стек-трейс **проглатывается** error handler-ом и пользователю не виден. Чтобы найти причину, нужно:

**Источник №1 — Railway logs (точный stack trace):**
```
Railway → проект efficient-appreciation → env production → сервис edl-site
→ Deployments → последний Active → View logs
→ Поиск по строкам: "Unhandled exception in handler" или "Traceback"
```

**Источник №2 — таблица `events`:**
```sql
SELECT occurred_at, user_id, payload->>'type' as error_type,
       payload->>'error' as error_msg,
       payload->>'tb_tail' as traceback_tail
FROM events
WHERE event = 'unhandled_exception'
ORDER BY occurred_at DESC
LIMIT 20;
```

### 1.4 Гипотезы (для приоритезации диагностики)

**Гипотеза A (наиболее вероятная)**: Ошибка в `_ensure_user()` (`start.py:29-48`) при `session.commit()` после `log_event(event='bot_start')`.
- Если падает — error handler срабатывает, меню НЕ отправляется. Но в скрине меню есть → значит, эта гипотеза не подходит для `/start`.

**Гипотеза B**: Ошибка в `dialog.handle_text()` (`dialog.py`) — но `/menu` и `/start` это команды, MessageHandler с `~filters.COMMAND` их игнорирует. Не подходит.

**Гипотеза C (моя ставка)**: Ошибка происходит в **асинхронной побочной задаче**, запущенной хендлером (например, фоновый `log_event`, `register_user` middleware, `notifications.send_to_admin_chat`). Хендлер успевает вернуть меню, но через несколько мс падает побочка → глобальный error handler срабатывает уже как «отдельное» событие для того же update.

**Гипотеза D**: Двойная регистрация хендлера `/start` или `/menu` (повторно добавлен где-то ещё). Проверить — нет ли `app.add_handler(CommandHandler("start", ...))` где-то вне `register()`.

**Гипотеза E**: `update.message.text` где-то падает на NoneType. Например, в `_ensure_user:45` есть `(update.message.text or "")` — это безопасно, но в других местах может не быть фолбэка.

### 1.5 Первое действие нового чата

**STOP. Не правь код без данных.** Сначала:
1. Извлеки 20-50 последних `unhandled_exception` событий из БД (SQL из §1.3).
2. Открой Railway logs за последние 24 часа, найди первый Traceback.
3. **Только после этого** формируй гипотезу и план фикса.
4. Отчитайся пользователю: «нашёл такой-то exception в таком-то месте, гипотеза такая-то».

---

## 2. ЦЕЛИ АУДИТА

### 2.1 Бизнес-цели бота (что должно работать безупречно)

| Цель | Критерий «работает» | Бизнес-impact |
|---|---|---|
| **Продажа Чекапа за 9 000 ₽** | Юзер от `/start` доходит до `awaiting_manual_payment` за ≤5 минут без ошибок | Основной revenue |
| **Доставка Чекапа** | Юзер от `/checkup` доходит до получения PDF без зависаний FSM | Удержание клиента, NPS |
| **Захват лидов** | FAQ, Quiz, «Узнать подходит ли мне» — все доводят до контакта | Pipeline для всех тарифов |
| **Лист ожидания Спринта** | Юзер может оставить email на следующий поток | Будущий revenue |
| **152-ФЗ комплаенс** | Согласие на ПД явное, версионируется, есть `/delete_my_data` и `/export_my_data` | Юридическая защита |
| **Админ-операции** | Иван и Катя могут смотреть заявки и помечать `/mark_paid` без сбоев | Operational health |

### 2.2 Что нужно произвести (deliverables)

По итогу аудита в новом чате должны появиться файлы:
1. `docs/qa_audit_2026-05-17/bug_log.md` — все найденные баги (с severity, шагами, причиной).
2. `docs/qa_audit_2026-05-17/gap_log.md` — функционал, который должен быть, но отсутствует.
3. `docs/qa_audit_2026-05-17/test_report.md` — pass/fail по тест-кейсам §6-§9 этого ТЗ.
4. `docs/qa_audit_2026-05-17/improvement_plan.md` — приоритезированный план доработки (P0/P1/P2).
5. **PR с фиксом** критичного бага из §1 (после подтверждения пользователя).
6. **Новые pytest-тесты** на регрессию найденных багов.

---

## 3. ИСТОЧНИКИ ПРАВДЫ

| Файл | Назначение |
|---|---|
| `/BOT_TZ_v3.md` (~1500 строк) | **Основное ТЗ v3** — все требования к функционалу. Сюда обращаться при любом вопросе «должно ли это работать». |
| `/BOT_TZ.md` (~150 строк, старая v1) | Устаревшее, для контекста истории. |
| `/edl-os-bot/docs/TZ_v3_1_hardening_patch.md` (~673 строк) | **Hardening patch v3.1** — security, rate-limits, anti-injection, quality checks. Дополняет v3. |
| `/edl-os-bot/docs/threat_model.md` (~99 строк) | Матрица угроз T1–T11, sandbox принципы. |
| `/edl-os-bot/docs/post_beta_quality_playbook.md` (~214 строк) | Что **не** менять без регресса (prompts, segment.py, llm.py). |
| `/edl-os-bot/docs/runbook.md` (новый, ~143 строки) | Диагностика типовых проблем. |
| `/edl-os-bot/docs/release_checklist.md` (новый, ~45 строк) | Gate-лист перед каждым релизом. |
| `/edl-os-bot/docs/voc_ritual.md` | Процесс работы с Voice of Customer. |
| `/docs/qa_pr18_checkup_content_findings.md` | Findings прошлой QA-сессии PR #18 (Чекап). |
| `/docs/qa_pr18_smoke_results.md` | Smoke-результаты PR #18. |
| `/edl-os-bot/src/core/config.py:Settings` | Source of truth по env-переменным. |

При расхождениях приоритет: **TZ_v3_1_hardening_patch.md > BOT_TZ_v3.md > runbook.md > код**.

---

## 4. КАРТА БОТА (что есть в коде на 17.05.2026)

### 4.1 Команды (registry: `edl-os-bot/src/bot/handlers/__init__.py:87-110`)

| Команда | Хендлер | Назначение |
|---|---|---|
| `/start` | `start.start_command` | Меню + deep-link routing + создание юзера |
| `/help` | `start.help_command` | Список команд |
| `/menu` | `start.menu_command` | Повторное меню |
| `/reset` | `start.reset_command` | Очистить `context.user_data` (FSM) |
| `/audit` | `audit.audit_command` | Лендинг Чекапа в боте |
| `/audit_sample` | `audit.audit_sample_command` | Пример отчёта |
| `/checkup` | `checkup.checkup_command` | Запуск FSM 20 вопросов (только paid) |
| `/refund` | `refund.refund_command` | Возврат в течение 14 дней |
| `/faq` | `faq.faq_command` | Rules-based FAQ |
| `/quiz` | `quiz.quiz_command` | 12-вопросный Founder OS Score |
| `/privacy` | `privacy.privacy_command` | Управление ПД |
| `/delete_my_data` | `privacy.delete_my_data_command` | Удаление ПД |
| `/export_my_data` | `privacy.export_my_data_command` | JSON-выгрузка ПД |
| `/admin` | `admin.admin_command` | Админ-панель |
| `/admin_login` | `admin_login.admin_login_command` | HMAC-сессия |
| `/admin_logout` | `admin_login.admin_logout_command` | Выход |
| `/mark_paid` | `admin.mark_paid_command` | Ручная отметка оплаты |
| `/applications` | `admin.applications_command` | Список заявок |
| `/emails_dump` | `admin.emails_dump_command` | CSV-выгрузка email |
| `/beta_summary` | `admin.beta_summary_command` | Сводка беты |
| `/bugs` | `bugs.bugs_command` | Bug-report'ы (админ) |
| `/feedback` | `feedback.feedback_command` | ОС (админ) |

### 4.2 Callback patterns

`consent:*`, `menu:*`, `segment:*`, `audit:start_purchase`, `audit:cancel_collection`, `audit:notify_waiting`, `offer:*`, `refund:request:*`, `privacy:*`, `quiz:ans:*`, `quiz:cancel`, `faq:show:*`, `admin:*`, `admin_login:hint`, `checkup:*`, `bugreport:*`, `bug:*`, `feedback:*`, `waitlist:*`.

### 4.3 Свободный текст

`MessageHandler(filters.TEXT & ~filters.COMMAND, dialog.handle_text)` — FSM-маршрутизатор:
1. Audit FSM (await_full_name / await_email / await_company)
2. Refund FSM
3. Lead capture FSM (demo / diagnostic / sprint_waitlist / hero_summary)
4. Scope guard (off-topic)
5. Free-form dialog → Claude Haiku 4.5

### 4.4 Глобальный error handler

`__init__.py:40-85` — см. §1.

---

## 5. МЕТОДОЛОГИЯ QA

### 5.1 Тестовая пирамида

```
        ┌─────────────────┐
        │     E2E         │  Telegram реальный, прод/staging
        │   (manual)      │  ~30-50 сценариев
        └─────────────────┘
       ┌──────────────────┐
       │   Integration    │  pytest + asyncpg + Redis
       │     (auto)       │  ~30-50 тестов
       └──────────────────┘
      ┌────────────────────┐
      │       Unit         │  pytest, чистые функции
      │     (auto)         │  ~80-100 тестов
      └────────────────────┘
     ┌──────────────────────┐
     │   Regression LLM     │  python tests/run_regression_v3_1.py
     │  syco + adversarial  │  84 кейса, ~150-300₽/прогон
     └──────────────────────┘
```

### 5.2 Типы тестов (B2B-бот checklist)

| Тип | Что проверяем | Где |
|---|---|---|
| **Functional happy-path** | Сценарий проходит без ошибок | §6 этого ТЗ |
| **Negative** | Что будет если ввести мусор / пустую строку / эмодзи / 10000 символов | §7 |
| **Edge cases** | Двойной клик, race condition, отправка между шагами | §7 |
| **Security** | PD-leak, RBAC, rate-limit, SQL-i, prompt injection, secret leak | §8 |
| **Performance** | latency p50/p95/p99 | §9 |
| **Resilience** | Что если LLM down, Postgres down, Redis down | §10 |
| **Localization / тон** | Русский, «вы», без шаблонной AI-вежливости | §11 |
| **Accessibility** | Длинные сообщения (>4096 символов), много кнопок, эмодзи | §11 |

### 5.3 Принципы B2B Telegram-бота

1. **Каждый шаг FSM имеет «выход»** (отмена / возврат в меню).
2. **Идемпотентность** — повторное нажатие не дублирует записи в БД.
3. **Атомарность** — `session.commit()` либо весь шаг сохраняется, либо ничего.
4. **Никогда не показывать stacktrace юзеру** — только friendly fallback.
5. **Не теряем введённые данные при `/reset`** — БД нетронута, только in-memory FSM.
6. **Concurrency-safe** — два сообщения подряд не ломают порядок состояний.
7. **Тестовый аккаунт не отличается от прод-юзера** — нет hardcoded флагов.
8. **Уведомления в `ADMIN_CHAT_ID` не зависят от ответа юзеру** — fire-and-forget.

---

## 6. ПЛАН ТЕСТ-КЕЙСОВ (FUNCTIONAL)

> Формат: `[TC-AREA-NNN] Название` — Шаги — Ожидаемый результат — Что проверяем в БД.

### 6.1 Onboarding (start, menu, help, reset)

| ID | Сценарий | Ожидание | DB |
|---|---|---|---|
| TC-START-001 | Новый юзер `/start` без payload | Приветствие + меню с 11 кнопками. 0 ошибок. | `users` +1 row, `events` `bot_start` +1 |
| TC-START-002 | Повторный `/start` тем же юзером | Меню (без приветствия) | Дубля `users` нет, `events` `bot_start` +1 |
| TC-START-003 | `/start audit` (deep-link) | Сразу аудит-флоу, минуя меню | `events` `bot_start` payload содержит `payload=audit` |
| TC-START-004 | `/start demo`, `/start diagnostic`, `/start sprint_waitlist`, `/start hero_summary` | Lead capture запускается | соответствующий event |
| TC-START-005 | `/start audit_sample` | sample PDF + CTA на покупку | `events` `sample_requested` |
| TC-START-006 | `/start quiz` | Quiz запускается | `events` `quiz_started` |
| TC-START-007 | `/start unknown_payload_xyz` | Меню (фолбэк) | event с `payload=unknown_payload_xyz` |
| TC-START-008 | **`/start` БЕЗ дубль-сообщения «Что-то пошло не так»** | Только меню, без error-fallback | `events` `unhandled_exception` НЕ +1 |
| TC-START-009 | `/menu` | Только меню | Никаких новых rows кроме, возможно, `events` |
| TC-START-010 | **`/menu` БЕЗ дубль-сообщения «Что-то пошло не так»** | Только меню | `unhandled_exception` НЕ +1 |
| TC-START-011 | `/help` | Список команд, корректно отформатирован | — |
| TC-START-012 | `/reset` | «Контекст сброшен», `context.user_data` пуст | `users` НЕ затронут |
| TC-START-013 | Каждая кнопка main_menu (`menu:audit`, `menu:demo`, …) | Соответствующий хендлер запускается | events |

### 6.2 PD Consent (consent.py + consent.py core)

| ID | Сценарий | Ожидание |
|---|---|---|
| TC-CONSENT-001 | Первый раз доходишь до audit-флоу | Бот требует согласие на ПД (кнопки «Принимаю / Не принимаю») |
| TC-CONSENT-002 | Принимаешь | `users.consent_pd_given_at` ставится, `consent_pd_version='2026-05-11'` |
| TC-CONSENT-003 | Не принимаешь | Возврат в меню, ПД не собираются |
| TC-CONSENT-004 | Повторно входишь в audit-флоу — снова требует? | Согласие действует, не требует повторно (если версия не изменилась) |
| TC-CONSENT-005 | Изменить `PRIVACY_POLICY_VERSION` → войти в audit | Должно потребовать новое согласие |
| TC-CONSENT-006 | `/delete_my_data` → согласие удаляется | `consent_pd_given_at=NULL`, `pd_access_log` `delete` |

### 6.3 Audit FSM (`/audit` — покупка Чекапа)

`edl-os-bot/src/bot/handlers/audit.py:58-66` (states), 538 строк.

| ID | Сценарий | Ожидание | DB |
|---|---|---|---|
| TC-AUDIT-001 | `/audit` без аргументов | Интро Чекапа: «Базовый 9000 / Plus 14000», кнопки «Выбрать тариф» |  |
| TC-AUDIT-002 | Клик «Базовый» (`audit:start_purchase:base`) | Если ПД не дано → запрос согласия |  |
| TC-AUDIT-003 | После согласия | Запрос ФИО («Как к вам обращаться?») | FSM `await_full_name`, Application создан со status `new` |
| TC-AUDIT-004 | Ввод ФИО (3+ слова) | Запрос email | FSM `await_email`, `users.first_name`/`last_name` обновляется |
| TC-AUDIT-005 | Ввод корректного email | Запрос компании | FSM `await_company`, `users.email` |
| TC-AUDIT-006 | Ввод email «not-an-email» | Бот вежливо просит исправить, не двигает FSM | FSM остаётся в `await_email` |
| TC-AUDIT-007 | Ввод компании | Показ оферты с кнопками «Принимаю / Не принимаю» |  |
| TC-AUDIT-008 | Принимаю оферту | `PAYMENT_MODE=stub` → «Ждите счёт от Ивана…» НЕТ кнопки YooKassa | Application `status=awaiting_manual_payment`, `users.consent_offer_accepted_at` |
| TC-AUDIT-009 | После принятия оферты — бриф в `ADMIN_CHAT_ID` | Содержит UUID, segment, контакты | — |
| TC-AUDIT-010 | `inv_id` Application НЕ NULL | Sequence `applications_inv_id_seq` работает (см. миграцию 0002) | `SELECT inv_id FROM applications` |
| TC-AUDIT-011 | `audit:cancel_collection` в любой момент FSM | FSM сбрасывается, юзер в меню | `events` `audit_cancelled` |
| TC-AUDIT-012 | Повторный `/audit` поверх активной заявки | Бот ведёт себя корректно (либо resume, либо новая заявка — что определяет ТЗ?) | — |
| TC-AUDIT-013 | `/audit_sample` | Sample PDF/HTML отчёт отправляется | `events` `sample_requested` |
| TC-AUDIT-014 | Email с заглавными буквами «Test@Mail.RU» | Нормализация в lowercase (см. `test_contact.py`) | `users.email='test@mail.ru'` |
| TC-AUDIT-015 | Plus-тариф (`audit:start_purchase:plus`) | Application с `payload.plan='plus'`, бриф с правильной суммой 14000 | — |

### 6.4 Checkup FSM (`/checkup` — 20 вопросов, 4 слоя)

`checkup.py` (531 строка), `core/checkup_questions.py` (310 строк, 20 вопросов).

| ID | Сценарий | Ожидание |
|---|---|---|
| TC-CHECKUP-001 | `/checkup` без оплаты | Отказ: «сначала оплатите Чекап через /audit» |
| TC-CHECKUP-002 | `/checkup` после `mark_paid` | Интро + кнопка «Начать» |
| TC-CHECKUP-003 | Кнопка «Начать» | Q1 (strategy/s1_horizon): «Опишите ваш бизнес через 3 года…» |
| TC-CHECKUP-004 | Короткий ответ (<min_words=25 слов) | Бот мягко просит расширить, не двигает FSM |
| TC-CHECKUP-005 | Полноценный ответ | Q2, прогресс «2/20» |
| TC-CHECKUP-006 | Переход с Q5 → Q6 | Intro к слою sales |
| TC-CHECKUP-007 | Аналогично Q10→Q11 (operations), Q15→Q16 (finance) | Intro к каждому слою |
| TC-CHECKUP-008 | Q20 (последний) | После ответа: «Готовим отчёт, ~30 секунд» |
| TC-CHECKUP-009 | PDF сгенерирован | Отправлен в чат как документ |
| TC-CHECKUP-010 | `applications.checkup_pdf_url` заполнен | — |
| TC-CHECKUP-011 | `applications.checkup_started_at` и `checkup_completed_at` корректны | — |
| TC-CHECKUP-012 | `checkup_answers` содержит 20 строк для этой `application_id` | — |
| TC-CHECKUP-013 | Повторный `/checkup` после завершения | Отдаёт готовый PDF, не запускает новый FSM |
| TC-CHECKUP-014 | `/reset` посреди Чекапа | FSM сбрасывается, БД-ответы сохранены |
| TC-CHECKUP-015 | LLM-оценка качества (quality_passed) | Корректно для коротких/общих/детальных ответов |
| TC-CHECKUP-016 | Применение миграций 0006_admin_sessions и 0007_checkup_answers | `SELECT version_num FROM alembic_version` = `0007_checkup_answers` |
| TC-CHECKUP-017 | Все 20 вопросов имеют уникальные `key` и `order` | unit test `test_checkup_questions.py` |
| TC-CHECKUP-018 | Поле «Не знаю / не понимаю» | Бот предлагает пояснение/пример (см. `why_we_ask`) |
| TC-CHECKUP-019 | Скип вопроса — есть ли такая возможность? | См. ТЗ v3 на предмет «можно ли пропустить» |
| TC-CHECKUP-020 | Чекап Plus vs Base — отличаются ли вопросы или только глубина анализа? | Сверить с ТЗ |

### 6.5 Admin (auth, login, mark_paid, applications, beta_summary, emails_dump)

| ID | Сценарий | Ожидание | DB |
|---|---|---|---|
| TC-ADMIN-001 | `/admin_login` без аргумента | Подсказка по формату | — |
| TC-ADMIN-002 | `/admin_login WRONG_KEY` | «Неверный ключ» | rate-limit counter +1 |
| TC-ADMIN-003 | `/admin_login <CORRECT>` | «✅ Авторизованы на 8 часов» | `admin_sessions` +1 |
| TC-ADMIN-004 | `/admin_login WRONG_KEY` ×4 | После 3-й — `Слишком много попыток, заблокировано на час` | Redis `admin_login_attempts:<id>` ttl |
| TC-ADMIN-005 | После блокировки правильный ключ | Всё равно отказ до истечения lock | — |
| TC-ADMIN-006 | Через 1 час после блокировки | Можно снова логиниться | Redis ключ expired |
| TC-ADMIN-007 | `hmac.compare_digest` (constant-time) | Unit test `test_admin_session.py` | — |
| TC-ADMIN-008 | `/admin_logout` | Сессия отозвана | `admin_sessions.revoked_at` ставится |
| TC-ADMIN-009 | Команда `/applications` от не-админа | Отказ | event `admin_denied` |
| TC-ADMIN-010 | `/applications pending 10` | Список 10 свежих | — |
| TC-ADMIN-011 | `/applications paid 5` | Список оплаченных | — |
| TC-ADMIN-012 | `/applications all 50` | Пагинация | — |
| TC-ADMIN-013 | `/mark_paid <UUID> 9000 test-ref` | «✅ Помечена paid», юзеру личка | `applications.status='paid'`, `payments` +1, `refund_eligible_until=now+14d` |
| TC-ADMIN-014 | `/mark_paid <bad-uuid> 9000 ref` | «Не нашёл заявку» | — |
| TC-ADMIN-015 | `/mark_paid` дважды один UUID | Idempotent, второй раз «уже оплачена» | без дубля в `payments` |
| TC-ADMIN-016 | `/mark_paid <UUID> -100 ref` | Отказ (отрицательная сумма) | — |
| TC-ADMIN-017 | `/beta_summary` | Сводка отзывов и багов |  |
| TC-ADMIN-018 | `/emails_dump` | CSV всех email с `status=paid` |  |
| TC-ADMIN-019 | `/admin` info | Список доступных команд для админов |  |
| TC-ADMIN-020 | Сессия истекает через 8 часов | После 8 часов `/applications` требует повторный login |  |

### 6.6 LLM Dialog (свободный текст + scope guard + PD sanitize)

| ID | Сценарий | Ожидание |
|---|---|---|
| TC-LLM-001 | «Расскажи про чекап» | LLM отвечает по теме, помещается в max_tokens (600) |
| TC-LLM-002 | «Какая погода?» | Scope guard блокирует, canned-ответ «помогаю только с операционкой…» |
| TC-LLM-003 | «Зашли мой пароль admin@admin.com tel +79991112233» | В user_text для LLM — маскированные плейсхолдеры |
| TC-LLM-004 | Очень длинный (>5000 символов) текст | Корректная обработка, не падает |
| TC-LLM-005 | Только эмодзи 😀😀😀 | Scope guard блокирует |
| TC-LLM-006 | Пустое сообщение / пробелы | Бот игнорирует |
| TC-LLM-007 | LLM down (отключить `ANTHROPIC_API_KEY` в тесте) | Graceful: «Не могу сейчас ответить, напишите Ивану» |
| TC-LLM-008 | `ANTHROPIC_BASE_URL` (proxyapi.ru) реально проксирует | Запрос идёт через прокси |
| TC-LLM-009 | Запуск `python tests/run_regression_v3_1.py --smoke` | Pass 100% |
| TC-LLM-010 | Запуск `python tests/run_regression_v3_1.py --critical` | Sycophancy 5/5, adversarial 5/5 |
| TC-LLM-011 | Запуск полного регресса | 28 base ≥27, syco 5/5, adv 5/5 |
| TC-LLM-012 | Prompt injection в свободном тексте («ignore previous instructions…») | LLM не нарушает sandbox, отвечает по делу |
| TC-LLM-013 | Цена не выдумана (всегда 9000/14000/25000) | Регресс `test_pricing_consistency.py` |
| TC-LLM-014 | Имя VITACONSULT в публичном ответе | Зависит от `VITACONSULT_PUBLIC` (false до 22.05) — должно быть скрыто |

### 6.7 Privacy

| ID | Сценарий | Ожидание |
|---|---|---|
| TC-PRIVACY-001 | `/privacy` | Список согласий: ПД (дано/нет, версия), маркетинг, оферта |
| TC-PRIVACY-002 | Кнопка «Скачать мои данные» (`privacy:export`) | JSON с users + applications + events |
| TC-PRIVACY-003 | Кнопка «Удалить мои данные» | Подтверждение → soft-delete |
| TC-PRIVACY-004 | После удаления — повторный `/start` | Создаётся новый юзер (с тем же telegram_id?) — поведение по ТЗ |
| TC-PRIVACY-005 | `pd_access_log` пишется на каждое действие | `actor`, `action`, `fields` корректны |

### 6.8 FAQ

| ID | Сценарий | Ожидание |
|---|---|---|
| TC-FAQ-001 | `/faq` | Список 11 тем (из `core/faq.py`) |
| TC-FAQ-002 | Клик `faq:show:N` | Текст ответа |
| TC-FAQ-003 | Тексты не выдают LLM-«воду», звучат человечно | — |

### 6.9 Quiz (Founder OS Score)

| ID | Сценарий | Ожидание |
|---|---|---|
| TC-QUIZ-001 | `/quiz` | Q1 «выберите вариант» |
| TC-QUIZ-002 | Все 12 вопросов отвечены | Финальный score 0-100, рекомендация |
| TC-QUIZ-003 | `users.quiz_score` обновляется | — |
| TC-QUIZ-004 | `/quiz` повторно | Перезапуск или показ предыдущего? |
| TC-QUIZ-005 | Отмена `quiz:cancel` | Возврат в меню |

### 6.10 Lead Capture (demo/diagnostic/sprint_waitlist/hero_summary)

| ID | Сценарий | Ожидание |
|---|---|---|
| TC-LEAD-001 | «Бесплатное демо · 30 мин» из меню | Запуск flow, сбор контактов, бриф в `ADMIN_CHAT_ID` |
| TC-LEAD-002 | «Лист ожидания Спринта» | Сбор email, запись в `applications.type=sprint_waitlist` |
| TC-LEAD-003 | Diagnostic flow | Запись |
| TC-LEAD-004 | Hero summary (если есть) | — |

### 6.11 Refund

| ID | Сценарий | Ожидание |
|---|---|---|
| TC-REFUND-001 | `/refund` через 7 дней после оплаты | Список оплат + кнопка «Запросить» |
| TC-REFUND-002 | Клик «Запросить» | FSM: причина → подтверждение → `refunds` +1 row, статус `requested` |
| TC-REFUND-003 | `/refund` через 15 дней (вне окна) | «Окно возврата истекло» |
| TC-REFUND-004 | `/refund` повторный для уже запрошенного | «Заявка уже есть, ждите ответа» |
| TC-REFUND-005 | Бриф в `ADMIN_CHAT_ID` | Содержит причину и контакт |

### 6.12 Feedback / Bug Report

| ID | Сценарий | Ожидание |
|---|---|---|
| TC-FB-001 | Кнопка «💬 ОС по этому шагу» | FSM: категория → severity → comment → `feedback` +1 |
| TC-FB-002 | Под LLM-ответом кнопки 👍 / 🤔 / 💬 К Ивану | Каждая работает |
| TC-FB-003 | 🤔 «Неточно» | Записывает в `bot_errors` с привязкой к `message_log_id` |
| TC-FB-004 | Админ `/bugs` | Пагинация unresolved bugs |
| TC-FB-005 | Кнопки `bug:resolve/patched/ignore` | Меняет статус |

---

## 7. NEGATIVE / EDGE CASES

| ID | Сценарий | Ожидание |
|---|---|---|
| TC-NEG-001 | В FSM `await_email` ввели «12345» | Friendly fallback, FSM не двигается |
| TC-NEG-002 | В FSM `await_full_name` ввели emoji 🙂 | Fallback или принять? Сверить с ТЗ |
| TC-NEG-003 | Двойной клик по «Принимаю» в оферте | Одно событие, не два |
| TC-NEG-004 | Юзер пишет в момент когда бот печатает | Сообщения не теряются, FSM не путается |
| TC-NEG-005 | Юзер блокирует бота посреди FSM | Логирование, не валится с exception |
| TC-NEG-006 | Юзер пишет сообщение в 10000+ символов | Telegram сам обрежет до 4096, бот не падает |
| TC-NEG-007 | Сообщение с null-байтами или странными управляющими символами | Sanitize / обработка |
| TC-NEG-008 | Юзер отправляет аудио / фото / стикер вместо текста | Бот вежливо просит текст |
| TC-NEG-009 | `/mark_paid` при выключенной Redis | Деградация — должно ли работать? |
| TC-NEG-010 | DB down посреди FSM | Глобальный error handler + повторная попытка |

---

## 8. SECURITY

### 8.1 Чек-лист угроз (из `docs/threat_model.md`)

| ID | Угроза | Контроль | Как проверить |
|---|---|---|---|
| TC-SEC-001 | T1: PD-leak в LLM | `pd_sanitize.sanitize()` | `pytest test_pd_sanitize.py` |
| TC-SEC-002 | T2: off-topic в LLM | `scope_guard` | `pytest test_scope_guard.py` |
| TC-SEC-003 | T3: prompt injection | system prompt anti-injection | adversarial pack |
| TC-SEC-004 | T4: брутфорс `/admin_login` | Redis rate-limit (3/10 мин → блок 1ч) | TC-ADMIN-004 |
| TC-SEC-005 | T5: подмена админа через ENV | `is_admin()` строгая проверка | unit test |
| TC-SEC-006 | T6: кража AdminSession | `expires_at`, `revoked_at` | TC-ADMIN-020 |
| TC-SEC-007 | T7: SQL injection | SQLAlchemy ORM, нет f-string SQL | `grep -rn 'f".*SELECT' edl-os-bot/src/` пусто |
| TC-SEC-008 | T8: утечка секретов в логах | Логи не содержат `bot_token`, `anthropic_api_key` | `grep` логов |
| TC-SEC-009 | T9: открытый PG | `DATABASE_URL` internal | проверить Railway |
| TC-SEC-010 | T10: webhook без secret_token | заголовок `x-telegram-bot-api-secret-token` | если webhook |
| TC-SEC-011 | T11: PDF поломан / XSS в HTML | WeasyPrint sanitization | вручную PDF |
| TC-SEC-012 | Secret scanning в репо | `mcp__github__run_secret_scanning` | 0 alerts |
| TC-SEC-013 | События НЕ содержат сырых ПД | `SELECT payload FROM events` не содержит email/phone | вручную |
| TC-SEC-014 | `messages_log.text` содержит исходный текст — это OK? | Сверить с ТЗ и `pd_access_log` | — |

### 8.2 Защита от инъекций в Telegram

- Markdown injection в `username` — рендерится ли как `*текст*`? Должно — экранировать.
- Юзернейм типа `[click](http://evil.com)` — не должен превращаться в кликабельную ссылку.

---

## 9. PERFORMANCE

| Операция | SLA p50 | SLA p95 |
|---|---|---|
| `/start`, `/menu`, `/help` | <1s | <2s |
| Шаг FSM (без LLM) | <1.5s | <3s |
| LLM-ответ (свободный диалог) | <5s | <10s |
| Quality check Чекапа | <8s | <15s |
| Генерация PDF (WeasyPrint) | <10s | <30s |
| `/applications pending 50` | <2s | <4s |
| `/mark_paid` | <2s | <4s |

Если `ANTHROPIC_BASE_URL` через proxyapi.ru — добавить ~500ms к LLM-latency.

---

## 10. RESILIENCE

| Сценарий | Ожидаемое поведение |
|---|---|
| Anthropic API 500 | Retry 3 раза с backoff, потом graceful fallback |
| Redis down | rate-limit ломается, но бот всё равно отвечает (degradation) |
| Postgres down | Глобальный error handler, юзеру fallback |
| Telegram API rate-limit (429) | Pause/retry внутри PTB |
| Долгий ответ LLM (>30s) | Timeout, графт. |
| Отправка PDF упала | Retry, иначе уведомление Ивану через `ADMIN_CHAT_ID` |

---

## 11. ЛОКАЛИЗАЦИЯ / ТОН / UX

| Проверка | Метод |
|---|---|
| Все строки на русском | `grep -rn "[A-Za-z]\{10,\}" edl-os-bot/src/bot/texts.py` — должно быть мало |
| Тон «вы», деловой | Чтение `texts.py`, `handlers/*.py` reply_text |
| Без излишней эмоциональности | Нет «Спасибо большое огромное!», «Чудесно!» |
| Эмодзи умеренно | Не более 1-2 на сообщение |
| Длинные сообщения разбиты | <2000 символов на сообщение, не 4096 на пределе |
| Кнопки понятны | Длина текста ≤30 символов |
| Bold/italic корректны | Markdown V2 экранирование |
| Стикеры используются по правилам | `test_stickers.py` — нет для manufacturing/wholesale/hot stage |

---

## 12. GAP-АНАЛИЗ (чего может не хватать для бизнес-целей)

Не доказательство багов, а **гипотезы недостающего функционала**. Сверить с `BOT_TZ_v3.md` и `TZ_v3_1_hardening_patch.md`.

| Gap | Бизнес-impact | Сложность |
|---|---|---|
| **Брошенная корзина** — юзер дошёл до оферты, не оплатил → через 24/48ч напоминание | Конверсия | Средне (нужен scheduler) |
| **Брошенный Чекап** — юзер начал, не закончил → напоминание | Удержание клиента | Средне |
| **UTM-метки** из deep-link сохраняются для атрибуции продаж | Маркетинг ROI | Низко (есть payload в events?) |
| **Метрики воронки** /admin: start→audit→paid→checkup_started→completed | Operational | Низко |
| **A/B на CTA в меню** | Конверсия | Высоко |
| **Webhook на оплату** (когда YooKassa включат) | Автоматизация | Средне |
| **Retry отправки PDF** если упала | Доставляемость | Низко |
| **Queue/throttle для LLM** при пиковой нагрузке | Стабильность | Средне |
| **Health endpoint для синтетического мониторинга** | Observability | Низко |
| **Аналог Sentry/error tracking** (помимо `events`) | DevEx | Средне |
| **Локальная команда `/version`** — какая версия бота, какая последняя миграция | DevEx | Низко |
| **`/whoami`** — для самопроверки админа: «вы админ, сессия до 19:30» | DevEx | Низко |
| **Авто-эскалация если юзер 3 раза получил error** | Качество | Низко |
| **Cron-задача напоминания о приближении окна возврата** | NPS / sales | Средне |
| **Multi-language hint** (если юзер пишет по-английски — намёк) | Не приоритет | Низко |

---

## 13. WORKFLOW АУДИТА (как тестировщик идёт по шагам)

### Шаг A. Подготовка
1. Прочитать `BOT_TZ_v3.md` (1500 строк, выписать ключевые требования).
2. Прочитать `TZ_v3_1_hardening_patch.md` (security/quality дополнения).
3. Запустить локально (`docker compose up postgres redis -d`, `alembic upgrade head`, `python -m src.main`) — убедиться что тесты проходят: `pytest -v`.
4. Подключиться к Railway logs (live tail) и Postgres (read-only public URL).
5. Создать ветку `claude/qa-audit-<auto-suffix>`.

### Шаг B. Диагностика P0 бага (см. §1)
1. SQL по `events.unhandled_exception` за 24 часа → найти stack trace.
2. Railway logs → найти соответствующий traceback.
3. Локализовать строку в коде.
4. Воспроизвести в локальной среде (если возможно).
5. Сформулировать гипотезу, обсудить с пользователем.
6. Реализовать фикс + регресс-тест (pytest).
7. Commit + push + draft PR.

### Шаг C. E2E прогон по §6 (все ~110 тест-кейсов)
1. Для каждой группы (Onboarding, Audit, Checkup, …) — отдельная сессия в Telegram.
2. По ходу заполнять `docs/qa_audit_2026-05-17/bug_log.md`.
3. Каждый bug — с severity (P0/P1/P2/P3), шагами, ожиданием, фактом, ссылкой на файл/строку-кандидат.

### Шаг D. Negative / Edge (§7)
То же по списку.

### Шаг E. Security (§8)
1. Запустить все security-pytest.
2. Запустить `mcp__github__run_secret_scanning`.
3. Вручную попробовать prompt injection и SQL-i.

### Шаг F. Regression LLM (§6.6)
```bash
cd edl-os-bot
python tests/run_regression_v3_1.py --smoke   # 10 кейсов
# Если зелёный →
python tests/run_regression_v3_1.py --critical  # 30 кейсов
# Если зелёный → (платно!)
python tests/run_regression_v3_1.py             # 84 кейсов, ~150-300₽
```

### Шаг G. Performance (§9)
1. Замерить latency 10 раз для каждого SLA-операции.
2. Расчёт p50/p95.
3. Если выход за SLA — записать как P2.

### Шаг H. Gap-анализ (§12)
1. Сверить с TZ v3 + v3.1 — что обещано, чего нет.
2. Заполнить `gap_log.md`.

### Шаг I. Финальный отчёт
1. `test_report.md` — числа (passed/failed/blocked/skipped по разделам).
2. `improvement_plan.md` — что фиксить первым.

---

## 14. ШАБЛОН BUG-REPORT

```markdown
## [BUG-001] /start отвечает дублирующим сообщением

- **Severity**: P0 (Blocker)
- **Found in**: prod, 2026-05-17 17:26 МСК
- **TC**: TC-START-008
- **Test account**: tg_id=XXX

**Шаги:**
1. Открыть @edl_os_bot
2. Отправить /start

**Ожидание**: Приветствие + меню (1 сообщение от бота).

**Факт**: Приветствие + меню + сообщение «Что-то пошло не так на нашей стороне…» (2 сообщения).

**Logs (Railway)**:
```
[ERROR] src.bot.handlers: Unhandled exception in handler: <ExceptionType>
Traceback ...
```

**DB**:
```sql
SELECT payload FROM events WHERE event='unhandled_exception' AND ...
-- type=, error=, tb_tail=
```

**Гипотеза причины**: `src/.../...py:XX` — <описание>.

**Workaround**: пока нет.

**Fix predicted scope**: <файл>:<строки>, +регресс-тест.
```

---

## 15. ACCEPTANCE CRITERIA АУДИТА

- [ ] Корневая причина P0-бага (§1) найдена и задокументирована.
- [ ] PR с фиксом P0 создан как draft.
- [ ] Все ~110 тест-кейсов из §6 пройдены или явно отмечены skipped.
- [ ] Negative/Edge из §7 — пройдены.
- [ ] Security-pytest все зелёные, secret-scan чист.
- [ ] Regression LLM (минимум `--critical`) — зелёный.
- [ ] Performance проверен, выходы за SLA задокументированы.
- [ ] Gap-list составлен и приоритезирован.
- [ ] `test_report.md` с цифрами создан.
- [ ] `improvement_plan.md` с P0/P1/P2 создан.
- [ ] Все 4 markdown-документа закоммичены в ветку (PR draft).

---

## 16. ОЦЕНКА «10/10»

В финальном отчёте по аудиту — оценка состояния по шкале 1–10:
- Функционал: __/10
- Стабильность: __/10
- Security: __/10
- Производительность: __/10
- UX / тон: __/10
- Покрытие тестами: __/10
- Документация: __/10
- Соответствие ТЗ v3 + v3.1: __/10
- **Общая**: __/10

Плюс — топ-5 рисков на ближайший месяц и топ-5 рекомендаций.

---

## 17. ПРОМПТ ДЛЯ СТАРТА НОВОГО ЧАТА

Скопировать пользователю в первое сообщение нового чата с Sonnet:

```
Прочитай ТЗ полностью: /home/user/edl-site/docs/QA_AUDIT_TZ_v1_for_sonnet.md

Это полный QA-аудит Telegram-бота @edl_os_bot. На проде критичный
баг (см. §1): /start и /menu отдают одновременно меню И сообщение об
ошибке. Корневая причина неизвестна — глобальный error handler
проглатывает стек-трейс.

ПЕРВОЕ ДЕЙСТВИЕ — §1.5 ТЗ — извлеки реальный stack trace из Railway
logs И из таблицы events (event='unhandled_exception'). Не правь
код без данных.

После каждого крупного шага — отчитайся коротко и жди подтверждения.
Без явного «ok, продолжай» не пушить ничего в main.

Рабочая ветка: claude/qa-audit-<любой суффикс>.
```

---

## 18. ПРИЛОЖЕНИЕ A — Полезные SQL

```sql
-- Все unhandled exceptions за 24ч
SELECT occurred_at,
       payload->>'type' AS error_type,
       LEFT(payload->>'error', 200) AS error_msg
FROM events
WHERE event = 'unhandled_exception'
  AND occurred_at > now() - interval '24 hours'
ORDER BY occurred_at DESC;

-- Воронка конверсии за неделю
SELECT event, COUNT(DISTINCT user_id) AS users
FROM events
WHERE event IN ('bot_start','consent_given','application_created',
                'payment_succeeded','checkup_started','checkup_completed')
  AND occurred_at > now() - interval '7 days'
GROUP BY event
ORDER BY users DESC;

-- Топ-10 ошибок по типу
SELECT payload->>'type' AS error_type, COUNT(*)
FROM events
WHERE event = 'unhandled_exception'
GROUP BY error_type
ORDER BY 2 DESC
LIMIT 10;

-- Все админ-сессии активные
SELECT telegram_id, granted_by, granted_at, expires_at
FROM admin_sessions
WHERE expires_at > now() AND revoked_at IS NULL;

-- Заявки без оплаты старше 48 часов
SELECT id, user_id, type, status, created_at
FROM applications
WHERE status = 'awaiting_manual_payment'
  AND created_at < now() - interval '48 hours';

-- Брошенные Чекапы
SELECT id, user_id, checkup_started_at
FROM applications
WHERE checkup_started_at IS NOT NULL
  AND checkup_completed_at IS NULL
  AND checkup_started_at < now() - interval '24 hours';
```

---

## 19. ПРИЛОЖЕНИЕ B — Команды для пакетного тестирования

```bash
cd /home/user/edl-site/edl-os-bot

# Все unit-тесты
pytest -v --tb=short --maxfail=20

# Только security
pytest tests/test_pd_sanitize.py tests/test_scope_guard.py \
       tests/test_admin_auth.py tests/test_admin_session.py -v

# Импорты (smoke check)
pytest tests/test_imports.py -v

# Чекап content
pytest tests/test_checkup_questions.py tests/test_checkup_quality.py \
       tests/test_checkup_report.py -v

# Regression LLM (smoke)
python tests/run_regression_v3_1.py --smoke

# Regression LLM (critical = syco + adv)
python tests/run_regression_v3_1.py --critical

# Regression LLM (full, платно ~150-300 ₽)
python tests/run_regression_v3_1.py

# Поиск SQL-i рисков
grep -rn 'f".*SELECT\|f".*INSERT\|f".*UPDATE\|f".*DELETE' edl-os-bot/src/

# Поиск утечек секретов в логах
grep -rn 'bot_token\|anthropic_api_key\|secret_key' edl-os-bot/src/ | grep -iE "log|print"

# Secret scanning в репо
# (через MCP GitHub: mcp__github__run_secret_scanning)
```

---

## 20. ПРИНЦИПЫ РАБОТЫ В НОВОМ ЧАТЕ

1. **Никогда** не делать destructive операций (`DROP`, `git push --force`, `rm -rf`) без явного подтверждения.
2. **Root cause > быстрый фикс**. Если падает healthcheck — диагностировать причину, а не отключать healthcheck.
3. **Bug найден → сразу регресс-тест в pytest**. Иначе вернётся.
4. **Один PR — одна проблема**. Не миксовать P0-фиксы с рефакторингом.
5. **Перед merge всегда** — `release_checklist.md`.
6. **Документация — это код**. Меняешь функционал — обновляешь `runbook.md` и/или `BOT_TZ_v3.md`.
7. После 3 неудачных попыток исправить одну проблему — стоп, отчёт, эскалация пользователю.

---

_Конец ТЗ v1.0. Если в процессе аудита выявлено что-то новое — добавить раздел `§21. Findings during audit` и записать._
