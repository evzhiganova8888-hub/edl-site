# QA · Чекап v2.0 · Pre-Release Package

> **Что это:** пакет документов и автотестов для безопасного прод-релиза Чекапа v2.
> **Версия:** 21.05.2026.

---

## Состав пакета

| Файл | Когда использовать |
|------|---------------------|
| `qa_release_checklist_checkup_v2.md` | **Полный QA pass перед релизом** (90 мин). Все P0/P1/P2 пункты по риску. |
| `qa_smoke_checkup_v2.md` | **Быстрый чек перед каждым deploy** (10 мин). 5 ключевых сценариев. |
| `qa_threat_matrix_checkup_v2.md` | Audit рисков (L0/T0/L1/...). Включает найденные расхождения с офертой. |
| `qa_ux_patterns_tg_founders.md` | Принципы UX для нашей ЦА (фаундеры). Применять при review новых экранов. |
| `tests/test_checkup_v2_integration.py` | 43 интеграционных теста (Score routing, upsell, section break, numeric, short-text). |
| `tests/test_checkup_v2_security.py` | 17 security-тестов (XSS, prompt injection, edge cases). |
| `tests/test_checkup_v2_score.py` | 7 тестов формулы Score. |
| `tests/test_checkup_v2_blocks.py` | 14 тестов PDF блоков (3 teasers, 28 video scripts). |
| `tests/test_checkup_v2_fsm.py` | 9 тестов FSM helpers. |

**Покрытие тестами**: 347 passed, 0 failed, 1 skipped.

---

## ❗ Найденные блокеры (закрыть ДО релиза)

### L0.1 · Несоответствие refund_eligible_until оферте

**Проблема:** Код устанавливает `refund_eligible_until = payment_succeeded_at + 14d`. Оферта §6.4: «14 дней с момента **передачи Материалов**» (т.е. отправки PDF).

**Последствие:** если юзер проходит Чекап >14 дней (длинная пауза), окно возврата истечёт раньше передачи PDF — бот откажет в возврате, нарушая оферту.

**Решение (выбрать):**
- **Вариант A (рекомендую):** обновить код:
  ```python
  # core/payment_marking.py:91
  # Старое:
  app.refund_eligible_until = now + timedelta(days=REFUND_WINDOW_DAYS)
  # Новое:
  # Окно возврата открывается с момента передачи материалов (PDF).
  # Сейчас при оплате ставим payment_succeeded_at + 30d как буфер.
  # Реальное окно (PDF + 14d) устанавливается в tasks/generate_checkup_pdf.py
  # после успешной отправки PDF клиенту.
  app.refund_eligible_until = now + timedelta(days=30)  # буфер до отправки PDF
  ```
  + в `generate_checkup_pdf.py` после отправки:
  ```python
  app.refund_eligible_until = datetime.now(timezone.utc) + timedelta(days=14)
  ```
- **Вариант B:** обновить оферту §6.4 на «14 дней с момента **оплаты**» (юрист пересогласует).

### L0.2 · Текст возврата в боте может звучать как «условный»

**Проблема:** ТЗ упомянул «возврат если не смог внедрить ни одну рекомендацию». Оферта §6.1: «**Безусловный** возврат 100% за 14 дней. Причину указывать не нужно».

**Действие:** проверить `texts.py` все упоминания возврата. Если есть «если не внедрили» — заменить на «безусловный».

```bash
grep -rn "не смог\|не внедрил\|если не\|при условии" edl-os-bot/src/bot/texts.py edl-os-bot/src/bot/handlers/refund.py
```

---

## Запуск автотестов

### Полная регрессия
```bash
cd edl-os-bot
uv run --extra dev pytest -q --ignore=tests/run_regression_v3_1.py
# → 347 passed, 1 skipped (target)
```

### Только Чекап v2
```bash
uv run --extra dev pytest tests/test_checkup_v2_*.py -v
```

### Security регрессия
```bash
uv run --extra dev pytest tests/test_checkup_v2_security.py -v
```

---

## Pre-release ритуал (рекомендую)

1. **T-1 день**: прогон `qa_release_checklist_checkup_v2.md` (P0 обязательно, P1 ≥90%).
2. **T-0 утро**: `pytest -q` → 347+ passed.
3. **T-0 deploy**: Railway autodeploy после мержа.
4. **T-0 +5 мин**: `qa_smoke_checkup_v2.md` пройти руками на проде.
5. **T-0 +1 час**: проверить Sentry / Railway logs на ошибки.
6. **T+1 неделя**: VoC review через `/beta_summary`.

---

## Контакты при инциденте

- Технические проблемы: Railway → Observability → ERROR-логи за час.
- Юридические вопросы: оферта `/legal/offer-checkup-2026-05.html` + юрист.
- Срочно: `ADMIN_CHAT_ID` уведомления + Иван `@lvanKhudyakov`.

---

*EDL OS · QA Checkup v2 Package · 21.05.2026*
