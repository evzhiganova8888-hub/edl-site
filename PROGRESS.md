# EDL OS Bot — Прогресс разработки

**Канонический документ:** [BOT_TZ_v3.md](BOT_TZ_v3.md) + [edl-os-bot/docs/TZ_v3_1_hardening_patch.md](edl-os-bot/docs/TZ_v3_1_hardening_patch.md)
**Бот:** [@edl_os_bot](https://t.me/edl_os_bot) (Online, Railway, EU West)
**Сайт:** https://elephantdreams.ru
**Статус:** MVP v3.1 hardened. Готов к Этапу 2 (платежи), ждём Robokassa-аккредитацию + финальный текст оферты от юриста.

---

## ✅ Сделано

### Этап 1 — Каркас (PR #1)
- Скелет проекта `edl-os-bot/` по §15 ТЗ v3
- docker-compose: Postgres 16 + Redis + бот + Celery worker/beat
- БД схема (Alembic 0001–0004): users, applications, payments, refunds, events, messages_log, pd_access_log, feature_flags, bot_errors
- 8+1 сегментов с под-профилями и маркер-словами
- 152-ФЗ согласие с hash версии политики
- Стикеры segment-aware (60% рандомизация, блокировка на manufacturing/wholesale/hot)
- PD-санитайзер перед отправкой в LLM (10 паттернов: email/телефон/ИНН/карта/TG/секреты/имя)
- Anthropic Claude Haiku 4.5 + prompt caching + temperature override
- Hand-off SLA-правила по сегментам
- 7 deep-link routes
- 12 команд: /start, /menu, /help, /audit, /audit_sample, /privacy, /delete_my_data, /export_my_data, /reset, /faq, /refund, /admin
- 24 промпт-файла + KB 7 файлов

### Этап 2 — Оплата + полные сценарии (PR #1)
- **Robokassa**: build_invoice_url с MD5-подписью и Receipt 54-ФЗ
- **Полный /audit**: FSM сбор ФИО → email → компания → оферта → Robokassa invoice
- **1-click /refund**: 14-дневное окно, опциональная причина post-action, dedup на повторы
- **Celery beat**: refund_check раз в час + weekly_voc по Пн 09:30 МСК
- **lead_capture.py**: общий FSM для demo/diagnostic/sprint_waitlist/hero_summary
- **Бриф в ADMIN_CHAT_ID**: при оплате, заявке, возврате
- **Webhook endpoints**: `/payments/robokassa/result`, `/success`, `/fail`
- **Чекап Plus 14 000 ₽** (с видео Кати) — отдельный SKU

### Этап 3 — Quiz + FAQ + админка + регрессия (PR #1)
- **Quiz Founder OS Score**: 12 вопросов, балл 0–100, рекомендация продукта
- **FAQ rules-based**: 11 Q&A, без LLM
- **Feature flags**: VITACONSULT_PUBLIC с обязательной причиной + audit-log
- **Админка REST API**: /admin/stats, /admin/applications, /admin/payments, /admin/users, /admin/flags, /admin/bot_errors
- **/admin команда в боте**: сводка + toggle VITACONSULT (через FSM с reason)
- **Регрессия 18 кейсов** + расширение до v3.1: sycophancy_pack (5/5) + adversarial_pack (5/5) = 28 кейсов × 3 температуры

### v3.1 Hardening (PR #2 + #3)
- **Anti-sycophancy** директива в base.md (Sharma et al.)
- **Honest AI disclosure** в welcome: «AI-помощник на Claude Haiku 4.5»
- **Anti-impersonation**: блокировка попыток «я — Катя/Иван/Антон/Данил/Дарья/Вероника/admin/root/dev»
- **Fake-empathy phrases** в запрещённые (Perry et al.): «понимаю как вам тяжело» → диагноз
- **Anti-funnel CTA**: «когда Чекап не подходит» — выкидываем нерелевантных, growth-loop
- **Threat model** + sandbox (LLM = только текст, никаких tool-calls из чата)
- **Rate limits**: 10 msg/min, 100/hr, 50k tokens/day, 3 payment/hr (fail-closed)
- **Input validation**: 4000 chars + control chars + ZW/bidi-override
- **VoC ритуал**: bot_errors таблица + кнопка «⚠️ Ответ неверный» под каждым ответом + weekly_voc Celery
- **Memory/continuity**: recap прошлых обращений при возврате через 24+ ч (с sanitize_pd на previews)
- **LLM fallback**: FAQ-only при недоступности Anthropic / превышении квоты
- **Holiday calendar РФ** 2026–2027 в working_hours
- **«Написать Ивану напрямую»** на каждом экране (D.2 mutualism)
- **Docs**: threat_model.md, voc_ritual.md, TZ_v3_1_hardening_patch.md, pricing-consistency test

### Юридический baseline (PR #4)
- **`legal/offer.html`** (редакция Май 2026): 14 разделов, закрыто 4 P0 + 12 P1 + 5 P2 из AI-юр-ревью.
  Реквизиты ИП заполнены: ИНН 027507994838, ОГРНИП 325028000082251, СФР 1377064587, ОКПО/ОКАТО/ОКТМО.
  Юр-значимые сообщения через e-mail/Telegram по ст. 165.1 ГК РФ.
  Адрес претензий: evzhiganova8888@gmail.com · +7 (917) 430-84-26.
- **Версионирование**: `/legal/offer/2026-05/`
- **`legal/LAWYER_BRIEF.md`**: 3 этапа (12–18к / 15–25к / 5–10к), 11 прямых вопросов юристу.

### Сайт ↔ бот
- Все 8 deep-links из §1 ТЗ v3 работают
- 8 CTA сайта ведут в @edl_os_bot с правильными `?start=` параметрами

---

## 🛣 Что дальше — Roadmap

### Спринт 2 · Запуск платежей (1–2 недели)

| # | Что | Кто | Срок |
|---|---|---|---|
| 1 | Юр-консультация по [`legal/LAWYER_BRIEF.md`](legal/LAWYER_BRIEF.md) — Этап 1 (оферта) | Юрист (12–18к ₽) | 5–7 раб. дней |
| 2 | Robokassa: аккредитация ИП Жигановой Е.В. (ИНН 027507994838 · ОГРНИП 325028000082251) | Катя + Robokassa | 3–5 раб. дней |
| 3 | После аккредитации — `ROBOKASSA_*` env-vars в Railway | Катя | 5 мин |
| 4 | Финальный текст оферты от юриста → заменить `legal/offer.html` | Катя | 1 день |
| 5 | Anthropic API key + $30 на тест → `ANTHROPIC_API_KEY` в Railway | Катя | 10 мин |
| 6 | Прогон регрессии v3.1 (28 × 3T = 84 вызова, ~$3) → цель: 23/28 на T=0.0, 22/28 на T=0.3, 21/28 на T=0.7, sycophancy 5/5, adversarial 5/5 | Катя | 30 мин |

### Спринт 3 · Артефакты Чекапа и контент (1 неделя)

| # | Что | Кто | Срок |
|---|---|---|---|
| 7 | Обезличенный PDF отчёта Чекапа → `edl-os-bot/assets/audit_sample.pdf` (HTML-шаблон уже есть) | Катя | 1 день |
| 8 | Видео-разбор Кати — sandbox 15 типовых видео или решение по варианту B/C (D.4) | Катя | 1 нед |
| 9 | Юр-консультация Этап 2 (152-ФЗ + Anthropic API заключение) | Юрист (15–25к ₽) | 7–10 раб. дней |
| 10 | 3 живых респондента из КСДВ для регрессии (1× manufacturing, 1× services_legal, 1× marketplace_accounting) | Катя | 1 нед |

### Спринт 4 · Релиз и оптимизация (после защиты #2)

| # | Что | Кто | Срок |
|---|---|---|---|
| 11 | Через `/admin` toggle VITACONSULT_PUBLIC=true с обязательной причиной | Катя | 10 сек |
| 12 | Первая итерация VoC ритуала по [`docs/voc_ritual.md`](edl-os-bot/docs/voc_ritual.md) | Иван + Катя | 30 мин/нед |
| 13 | A/B-тесты welcome-сообщений по первым 100 пользователям | Катя + Иван | 2 нед |
| 14 | Calendly API webhook для прямого бронирования из бота (опц.) | Катя | 1 день |
| 15 | Telegram OAuth для REST-админки (заменить header `X-Telegram-User-Id`) | Катя | 1 день |
| 16 | Grafana дашборд (метрики уже доступны через `/admin/stats` JSON) | DevOps | 4 часа |
| 17 | Sandbox-видео из набора Кати → реальные стикеры через sendSticker + file_id | Катя | 2 часа |

---

## Текущие открытые вопросы

| # | Вопрос | Кто решает | Дедлайн |
|---|---|---|---|
| Q1 | Видео-bottleneck (D.4 v3.1): вариант C выбран (Plus 14k за видео). Подтвердить, или уйти в B (только warm/hot)? | Катя | до Спринта 2 |
| Q2 | AI-evaluator для sycophancy_score (I.2): вручную или второй LLM-вызов? Сейчас — вручную | Иван + Катя | после первых 30 диалогов |
| Q3 | OGRN и адрес для корреспонденции — в оферте заменены на §165.1 ГК (e-mail). Юрист подтвердит | Юрист | Этап 1 |
| Q4 | Memory/continuity (P2): сейчас работает, но recap-snippets не учитывают согласия отзыв. Если пользователь отозвал ПД и вернулся через неделю — recap всё ещё подгружается. Нужен ли отдельный гард? | Юрист + Катя | Этап 2 (152-ФЗ) |

---

## Структура репо

```
edl-site/
├── BOT_TZ_v3.md                ← каноническое ТЗ
├── PROGRESS.md                 ← этот файл
├── SESSION_HISTORY.md          ← история сессий
├── *.html                      ← сайт; все CTA → @edl_os_bot с deep-link
├── legal/
│   ├── offer.html              ← оферта (Май 2026)
│   ├── offer/2026-05/          ← версионированный snapshot
│   ├── privacy.html            ← политика 152-ФЗ
│   ├── terms.html              ← terms
│   └── LAWYER_BRIEF.md         ← ТЗ юристу с 3 этапами
└── edl-os-bot/                 ← бот по ТЗ v3 + v3.1 hardening
    ├── docker-compose.yml      ← Postgres + Redis + bot + Celery
    ├── Dockerfile, pyproject.toml, alembic.ini, .env.example
    ├── alembic/versions/       ← 4 миграции
    ├── assets/                 ← audit_sample.html (PDF — за Катей)
    ├── docs/                   ← threat_model, voc_ritual, v3.1 patch
    ├── src/
    │   ├── main.py             ← FastAPI: /webhook + /payments + /admin
    │   ├── bot/handlers/       ← 13 хендлеров
    │   ├── core/               ← config, segment, consent, offer, flags, quiz,
    │   │                          faq, contact, working_hours (с праздниками РФ),
    │   │                          handoff, pd_sanitize, stickers, llm, prompts,
    │   │                          notifications, payments/robokassa,
    │   │                          rate_limit, input_validation, memory
    │   ├── prompts/            ← BASE + 9 verticals + 5 stages + 9 handoff
    │   ├── knowledge_base/     ← 6 файлов (методология, кейсы, гарантия, возражения)
    │   ├── db/                 ← SQLAlchemy 2.0 + 9 таблиц + репозитории
    │   ├── admin/              ← FastAPI routes + auth
    │   └── tasks/              ← Celery (refund_check + weekly_voc)
    └── tests/                  ← regression v3 + v3.1 (28 × 3T) + pricing-consistency
```

---

## Контакты

- Бот: [@edl_os_bot](https://t.me/edl_os_bot)
- Sales: [@lvanKhudyakov](https://t.me/lvanKhudyakov)
- Канал: [@edl_os](https://t.me/edl_os)
- Заказчик: ИП Жиганова Е.В. · ИНН 027507994838 · ОГРНИП 325028000082251
- Контакт: [@evzhiganova](https://t.me/evzhiganova) · +7 (917) 430-84-26 · evzhiganova8888@gmail.com
