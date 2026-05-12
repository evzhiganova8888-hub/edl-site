# Post-beta quality playbook · EDL OS Bot

**Кому:** Кате (или Claude в новом окне через @-загрузку этого файла).
**Когда:** после закрытия беты 19 мая 2026 — перед тем как внедрять собранную ОС.
**Цель:** не сломать AI-поведение, которое уже прошло регрессию 30/30 (critical) и 27+28+27/28 (full @ T=0/0.3/0.7) + syco 5/5 + adv 5/5.

---

## TL;DR — что точно работает на момент 12 мая 2026

| Артефакт | Статус | Где |
|---|---|---|
| `base.md` — trigger-based playbook с Триггером 0 «Опиши Чекап» и 6 триггерами + few-shot examples | PASS full | `src/prompts/base.md` |
| `verticals/services_legal.md` — нарратив с обязательными «инфраструктура» / «собственник» | PASS | `src/prompts/verticals/` |
| `regression_v3.json` v3.2 — семантические `must_include_any` (5-10 синонимов) | 28 кейсов | `tests/` |
| `sycophancy_pack.json` v3.2 | 5/5 | `tests/` |
| `adversarial_pack.json` v3.2 | 5/5 | `tests/` |
| Anti-syco правила | Различают самозаявление vs контекст бизнеса | `base.md` §I.4 |
| Beta-UI: feedback bucket + кнопки + миграция 0005 | Не трогает промпт | `feat/beta-feedback-bucket` |

**Принципиально:** beta-PR (`feat/beta-feedback-bucket`) **не редактирует ни одного промпта** — только UI/FSM/миграция. Поэтому регрессия 12 мая = регрессия 19 мая (если за бету сами руками промпт не правили).

---

## Что НЕ менять без re-run регрессии

Изменения в этих файлах **обязательно** требуют `./tests/regression.sh critical` (минимум) перед commit'ом:

1. `src/prompts/base.md` — особенно:
   - **§I.4 anti-sycophancy** (рулил syco_s2, syco_s5)
   - **Trigger 0 «Опиши Чекап»** — 4 опорных точки, без них audit_contents fail (3/3 в первой full)
   - **Trigger по VAT/дроблению** — рулил VITACONSULT leak
   - **Few-shot examples** — заменили negative instructions, это удержание best-practice 2026
2. Любой файл в `src/prompts/verticals/` — менять только если segment-specific фидбек прямо в одно место.
3. `src/core/segment.py` — маркеры детекции сегмента влияют на выбор vertical → влияют на ответ.
4. `src/core/llm.py` — temperature, max_tokens, system prompt сборка. Сейчас 3 cache блока (shared / per-segment / dynamic) — порядок критичен.

Изменения тут **не** требуют re-run (UI/инфраструктура):
- `src/bot/*` (handlers, keyboards, texts) — UX, не AI
- `src/db/*` — модели, миграции
- `src/tasks/*` — Celery beat
- `src/admin/*`, `src/core/feedback.py`, `src/core/rate_limit.py` etc.

---

## Workflow для применения собранной ОС после беты

### Шаг 1. Снять снимок ОС (Катя одна, 15 мин)

```bash
# В @edl_os_bot Кате:
/bugs export       # md-выгрузка неразобранных bug-report'ов
/feedback export   # md-выгрузка структурированной ОС
```

Скопировать оба md в один файл `voc_2026-05-19.md`. Плюс — последний `weekly_voc/2026-05-19.json` из репо.

### Шаг 2. Кластеризовать (Катя + Claude, 30 мин)

Загрузить `voc_2026-05-19.md` в чат + сказать:
> «Кластеризуй ОС по 3 группам: (1) UX/тексты — правим без re-test, (2) промпт — требует регрессии, (3) скоуп Спринта 2 — не делаем сейчас. Для каждой группы — приоритеты P0/P1/P2.»

Ожидаемый результат — таблица «комментарий → группа → приоритет → файл».

### Шаг 3. Применить группу 1 (UX/тексты)

Можно безопасно править:
- `src/bot/texts.py` — формулировки
- `src/bot/keyboards.py` — кнопки, порядок
- `src/bot/handlers/*.py` — FSM-логика, но **не** содержание ответов AI
- `docs/*` — пост в канал, FAQ

После — `pytest tests/ -x --ignore=tests/run_regression*.py` (~30 сек, без API-ключа). Эта папка покрывает консент, оферту, payments, segment, working_hours и т.д. — всё, что не LLM. Если зелено — push.

### Шаг 4. Применить группу 2 (промпт) — с регрессией

**Правило одной правки:** один PR = одно изменение в промпте. Не «причёсываю base.md» — одна конкретная правка под конкретный фидбек.

```bash
# Подготовка
git checkout -b fix/prompt-<тема>

# Правка base.md или verticals/*.md (одна, точечная)

# Re-run на текущем main как baseline (если ещё не делали)
./tests/regression.sh critical   # ~80 ₽, 3 мин — syco + adv

# Re-run на ветке с правкой
./tests/regression.sh critical

# Если зелено — push, ставим в очередь к merge
# Если красно — diff отчётов, понимаем что сломали, чиним
```

**Перед merge'ем — `./tests/regression.sh full` (~300 ₽, 10 мин) на финальной версии.** Без full PASS — не вливаем в main.

### Шаг 5. Применить группу 3 (скоуп Спринта 2)

Отложить в `docs/sprint_2_backlog.md` с пометкой источника (FB#42 от @username). Эти ОС не теряются — они становятся требованиями к следующему спринту.

---

## Конкретные грабли, которые мы уже наступили

Чтобы не наступать снова:

### 1. SQLAlchemy autoincrement не работает для не-PK колонок
**Симптом:** `inv_id NULL violation` при создании Application.
**Фикс:** `server_default=sql_text("nextval('applications_inv_id_seq')")`.
**Где:** `src/db/models.py:75`.

### 2. Python 3.9 + PEP 604 `int | None`
**Симптом:** `eval_type_backport` нужен для regression в 3.9.
**Фикс:** уже в `tests/requirements-regression.txt`. Не убирать.

### 3. T=0.7 «случайные» fail-ы
**Не fix-ить точечно** одним cherry-pick'ом — это шум температуры. Если 27/28 на T=0.7 при 28/28 на T=0/0.3 — это норма; full PASS, идём дальше. Цепляться за 100% на T=0.7 = перетюнить промпт под flaky test.

### 4. Anti-syco vs context conflict
**Симптом:** правило «не повторяй цифры пользователя» блокировало законное упоминание сегментного контекста.
**Фикс:** разделять самозаявление пользователя vs контекст бизнеса. Текст правила в `base.md §I.4`. Если правка anti-syco — проверять syco_s2 и regression_full одновременно.

### 5. audit_contents забывает «гарантия»
**Симптом:** AI описывает Чекап без упоминания гарантии возврата.
**Фикс:** Trigger 0 в `base.md` требует 4 опорных точки: тариф, что входит, гарантия, что НЕ подходит.

### 6. VITACONSULT leak до 22.05
**Симптом:** AI упоминает конкретный кейс до запуска паблик-нарратива.
**Фикс:** feature flag `VITACONSULT_PUBLIC` через `src/core/flags.py`. Промпт сам читает флаг.

### 7. String matching ломается на синонимах
**Симптом:** тест ждёт «возврат» — AI отвечает «refund / вернём деньги / страховка результата». Fail на правильном ответе.
**Фикс:** `must_include_any` со списком синонимов (5-10). Это уже встроено в `regression_v3.json` v3.2 — не возвращаться к literal matching.

### 8. PD-leak в инпутах
**Симптом:** пользователь пишет email/телефон/ФИО — он попадает в LLM-промпт обезличенным.
**Фикс:** `src/core/pd_sanitize.py`. Промпт получает `[EMAIL]`/`[PHONE]`-плейсхолдеры, не raw ПД.

### 9. Conflict 409 + Redis errors при двойном инстансе
**Симптом:** Telegram возвращает 409 если бот запущен дважды.
**Фикс:** один воркер на Railway, либо webhook-режим. Не запускать локально с тем же токеном.

### 10. FSM-конфликт между bug_report и audit
**Симптом:** юзер тапнул «⚠️ Ответ неверный» → отвлёкся → пошёл в /audit и пишет ФИО — оно съедается bug_report FSM.
**Митигация:** короткий комментарий + кнопка «Пропустить». Полного фикса нет — это известный trade-off.
**Beta:** feedback FSM поставлен последним в dialog.py, чтобы хотя бы FIO/email/refund-reason не страдали.

### 11. Cherry-pick через open PR
**Симптом:** Катя смержила первый коммит ветки → последующие push'и создают второй открытый PR.
**Фикс:** работать в чистой ветке от main. Перед merge — `git log feat/<branch>..main` должен быть пустой.

### 12. API-key leak в чате
**Симптом:** скрин с открытым `.env` или строкой `sk-...` попадает в чат.
**Фикс:** revoke в proxyapi → новый ключ → положить только в Railway env, не в репо.

---

## Чек-лист «беспроблемного» PR после ОС

Перед commit'ом проверь:

- [ ] Затрагивает только UX-файлы — нет правок `base.md`/`verticals/*`/`segment.py`/`llm.py`?
  - Да → `pytest tests/ -x --ignore=tests/run_regression*.py` достаточно.
  - Нет → обязательно `./tests/regression.sh critical` минимум.
- [ ] Один PR = одна тема? (Не «причёсываю всё».)
- [ ] В коммит-сообщении указан источник фидбека (FB#42 / Bug#17 / @username)?
- [ ] Если правил промпт — приложил diff отчёта регрессии в PR description?
- [ ] Если правил миграцию — `alembic upgrade head` локально проверен на пустой БД?
- [ ] Если правил кнопки/callbacks — callback_data < 64 байт? (Telegram limit.)
- [ ] Если правил GREETING/тексты — `parse_mode` соответствует содержимому (markdown vs plain)?
- [ ] Если меняешь stickers/temperature/max_tokens — это правка LLM-поведения, требует регрессию.

---

## Куда уходят ОС, которые НЕ внедрим в этом цикле

`docs/sprint_2_backlog.md` (создать после беты). Каждая отложенная ОС:
```
## FB#42 · @username · 2026-05-15
**Шаг:** offer · **Категория:** missing
**Комментарий:** «Не понял, что значит "не сможете внедрить"»
**Решение:** перенести в Sprint 2 (переписать оферту → юр.правка).
**Деадлайн:** июль 2026
```

Это закрывает контур — юзер не видит «черной дыры», у нас есть журнал.

---

## Команды-шпаргалка

```bash
# Smoke (1 мин, ~30 ₽) — sanity-check после мелкой правки
./tests/regression.sh smoke

# Critical (3 мин, ~80 ₽) — обязательно при правке anti-syco / adv
./tests/regression.sh critical

# Full (10 мин, ~300 ₽) — перед merge'ем в main любой prompt-правки
./tests/regression.sh full

# Юнит-тесты (30 сек, без API-ключа) — после UX-правок
pytest tests/ -x --ignore=tests/run_regression*.py --ignore=tests/run_regression_v3_1.py
```

---

## Что добавить в этот playbook, когда соберём ОС беты

(Заполняется после 19 мая.)

- [ ] Самые частые категории ОС → что это значит про слабые места UX
- [ ] Прогноз cost-of-change для каждого кластера
- [ ] Уроки про то, какие подсказки в feedback-form работают, какие — нет
