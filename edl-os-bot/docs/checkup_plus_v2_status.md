# Чекап Plus v2.0 — текущий статус и что осталось

Документ отслеживает соответствие реализации боту техническому заданию
«EDL OS · Чекап Плюс v2.0» от 21.05.2026. Обновляется по PR-ам.

## Готово на 22.05.2026 — PR #53 + текущий PR

### ✅ Условная гарантия возврата (PR #53)
- `texts.py`, `refund.py`, `offer.py`, 5 KB-файлов, `prompts/base.md`,
  шаблоны PDF — переписаны на формулировку «возврат при выполнении ОБОИХ
  условий».
- Регрессия: `tests/test_refund_language.py`.

### ✅ Видео от команды EDL OS (PR #53)
- Везде в клиентских поверхностях видео-разбор подписан как «команда
  EDL OS». ИП «Жиганова Екатерина Викторовна» оставлено как юр. оператор.
- Регрессия: `tests/test_video_attribution.py`.

### ✅ Промокод-engine 24ч TTL (PR #53)
- `core/coupon_engine.py`, миграция `0014_coupons.py`, команды
  `/diagnostika`, `/issue_coupon`, `/coupon_info`, `/confirm_payment`,
  celery-task `expire_coupons` каждые 15 минут.
- Регрессия: `tests/test_coupon_engine.py`.

### ✅ PDF-шаблон Екатерины (1509 строк) подключён (текущий PR)
- `templates/edl_chekap_template.html` — финальная вёрстка из ТЗ.
- 8 правок Екатерины применены:
  - #1 Юридически корректный блок гарантии (страница 17 Plus / 12 Base).
  - #2 «Катерина» → «Команда EDL OS» (избегая юр. идентификатора).
  - #3 Усиление страницы 2 — поле `executive_summary[].layer_impact`.
  - #4 Расширенный юр-футер из 5 пунктов на финальной странице.
  - #7 Альтернативы агентам — 3 пути в Plus (своими силами / найм /
    через наших агентов), запрет слова «окупается».
  - #8 Подписан как «команда EDL OS» — `personal_comment.signature_name`.
- Pipeline `core/checkup_pdf_v3.py`: Claude Haiku 4.5 → JSON → Jinja2 →
  WeasyPrint. Fallback на ARCHETYPE_FALLBACKS если Claude failed.
- Регрессия: `tests/test_checkup_pdf_v3.py` (включая render Jinja2 и
  forbidden-words guard).
- Демо-PDF Basic ≈ 97 KB, Plus ≈ 115 KB — соответствует ТЗ.
- **Активация в проде**: env `CHECKUP_PDF_V3_ENABLED=1`. По умолчанию
  выключен — старый v2 PDF продолжает рендериться.

### ✅ Архетипы 6 MVP + fallback (текущий PR)
- `core/checkup_archetypes.py` — все 6 пар сегмент × стадия из ТЗ §3.5
  + fallback по соседу.
- Бенчмарки `SEGMENT_STAGE_BENCHMARKS` (6 ячеек), `STAGE_WEIGHTS` для
  расчёта общего Score.
- Регрессия: `tests/test_checkup_archetypes.py`.

### ✅ 16 SPIN-вопросов (текущий PR)
- `core/checkup_spin_questions.py` — 16 SPIN-вопросов из ТЗ §3.3 в строгом
  порядке слоёв (4×4). Маркеры decline («не знаю / не считаем»).
- Регрессия: `tests/test_checkup_spin_questions.py`.

### ✅ SPIN FSM handler-модуль (текущий PR)
- `bot/handlers/checkup_spin.py` — pause/resume через `checkup_current_
  question_index`, 3 экрана-вставки между блоками, чекпоинты после
  каждого слоя, decline-обработка, прогресс-бар, restart-логика, запуск
  PDF-генерации после Q4.4.
- Регрессия: `tests/test_checkup_spin.py`.

### ✅ Миграция 0015_checkup_spin_v2 (текущий PR)
- `applications`: `archetype`, `report_id`, `spin_failsafe_warning_sent_at`.
- `checkup_answers`: `is_decline`, `decline_reason`.
- Аддитивная — старые 20-quiz Чекапы продолжают работать.

### ✅ Системный промпт для Claude Haiku 4.5 (текущий PR)
- `prompts/checkup_pdf_data_generator.md` — 10 принципов генерации из
  Приложения B ТЗ, статика для guarantee + legal_footer + next_step,
  список запрещённых слов.

## Что не вошло (требует отдельной сессии)

### ❌ Wire-up SPIN FSM в `/checkup` команду
- Текущая `bot/handlers/checkup.py:checkup_command` — flow на 20 quiz.
- SPIN-handler в `checkup_spin.py` готов, но НЕ подключён к команде
  `/checkup`. Wire-up — это:
  1. В `checkup_command` проверить env-флаг `CHECKUP_SPIN_V2_ENABLED`.
  2. Если включён И у заявки нет legacy-ответов → `start_spin_checkup`.
  3. В `dialog.handle_text` добавить вызов `handle_spin_text` перед
     остальными FSM-проверками.
  4. В `bot.handlers.__init__.register` добавить
     `CallbackQueryHandler(handle_spin_callback, pattern=r"^spin:")`.
- Без wire-up SPIN-handler не доступен пользователям, но модуль покрыт
  тестами и готов к включению.

### ❌ 5-минутный fail-safe «нет ввода»
- ТЗ §3.6: если клиент открыл вопрос и 5 минут молчит — бот отправляет
  сообщение «Заметила, что прошло 5 минут…».
- Требует setup PTB JobQueue или внешнего таймера. В текущей архитектуре
  бот не имеет JobQueue (только Celery beat для серверных задач).
- Реализуется одним из двух путей:
  - Celery beat-task каждую минуту сканирует `applications` где
    `checkup_last_active_at < now - 5min` И `spin_failsafe_warning_sent_at
    IS NULL` → отправляет уведомление и помечает.
  - PTB JobQueue с per-user job (отменяется при ответе).
- Колонка `spin_failsafe_warning_sent_at` в миграции 0015 уже есть.

### ❌ Полная локализация архетипов в SPIN вопросах
- Сейчас `SPIN_QUESTIONS` содержат канонический вопрос + situation, но
  без `good_answer_example[archetype]`. ТЗ §3.3 предполагает, что под
  каждый из 6 архетипов есть свой пример хорошего ответа.
- Реализуется как `core/checkup_spin_examples.py` — словарь
  `{question_id: {archetype: example_text}}`. 16 × 6 = 96 примеров.
  Тексты приложения A ТЗ — основа.
- Используется в SPIN-handler перед каждым вопросом для рендера блока
  «💡 Пример хорошего ответа».

### ❌ Автоматическая выдача купона T+48ч после Plus-видео
- Сейчас `/issue_coupon` — только ручная команда админа.
- В `notify_plus_video.py` или новой celery-task: после
  `plus_video_sent_to_client_at + 24h` автоматически выдавать купон.
- Engine `coupon_engine.issue_coupon` уже idempotent и готов.

### ❌ Согласие 152-ФЗ перед стартом SPIN-Чекапа
- ТЗ §9.3: отдельный экран consent перед Q1.1.
- Сейчас бот собирает консент при покупке (`bot/handlers/consent.py`),
  но для SPIN-флоу нужно явно показать ещё раз с упоминанием Claude.

### ❌ Деплой config
- В `.env.example` добавить:
  - `CHECKUP_PDF_V3_ENABLED=0` (включить вручную после ревью PDF).
  - `CHECKUP_SPIN_V2_ENABLED=0` (включить после wire-up).

## Зачем держать оба пути (v2 + v3)

- Прод-клиенты, начавшие 20-quiz Чекап до релиза v2.0, должны иметь
  возможность завершить старый flow с старым PDF — миграция чисто
  аддитивная.
- Feature-flag гарантирует rollback в случае проблем с Claude API
  (proxyapi.ru даун, rate limit, JSON-валидация).
- После пилота 5 клиентов Plus и стабилизации — выкатить
  `CHECKUP_*_ENABLED=1` всем и удалить старый код в следующем major.

## Acceptance criteria из ТЗ §11

| AC | Статус | Комментарий |
|---|---|---|
| AC1 happy-path Plus | ⚠ Частично | PDF v3 готов, SPIN FSM написан, но не wired в `/checkup` |
| AC2 happy-path Base | ⚠ Частично | То же |
| AC3 Pause/Resume | ⚠ Готов в handler-модуле | Тестируется только когда wire-up |
| AC4 Fail-safe 5 мин | ❌ | Колонка в миграции 0015 + хук в FSM есть, периодик не написан |
| AC5 Refund happy-path | ✅ | Условная гарантия + обоснование в refund.py (PR #53) |
| EC1 Claude failure → fallback PDF | ✅ | ARCHETYPE_FALLBACKS + рендер без падений |
| EC2 Dormant >30д | ⚠ | Pause/resume через q_idx работает, dormant-маркер не выставляется |
| EC3 Купон активирован, Иван 24ч не отвечает | ❌ | Эскалация не реализована |
