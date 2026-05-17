# Бэкенд для виджета + whitepaper-формы — что сделано и как деплоить

**Дата:** 2026-05-18
**Ветка:** `claude/website-v4-updates`
**Связано с:** [website_v4_status_2026-05-18.md](website_v4_status_2026-05-18.md)

---

## Что добавлено в edl-os-bot

### 1. Три новых HTTP-эндпоинта на FastAPI
| Эндпоинт | Что делает |
|---|---|
| `POST /widget/message` | Принимает сообщение от веб-виджета, ставит фоновую задачу на LLM (Claude Haiku), возвращает `202 Accepted`. Ответ улетает через SSE. Rate-limit 12 сообщ/мин на сессию. |
| `GET /widget/stream/{session_id}` | Server-Sent Events: клиент держит соединение, сервер пушит JSON-payload c полями `text` и `buttons`. Heartbeat каждые 15 сек чтобы Railway proxy не закрывал коннект. |
| `POST /leads/whitepaper` | Сохраняет email в `whitepaper_leads`, шлёт админу TG-нотификацию, возвращает `download_url`. Rate-limit 3 заявки/IP/мин. |

### 2. Quick-replies без LLM
Кнопки виджета («Что такое EDL OS?», «Сколько стоит?», «Пройти Founder OS Score», «Связаться с менеджером») и команда `/start` — обрабатываются захардкоженными ответами в [`src/widget/routes.py:_QUICK_REPLIES`](../edl-os-bot/src/widget/routes.py). «Связаться с менеджером» дополнительно шлёт алерт в `ADMIN_CHAT_ID`.

### 3. Любое другое сообщение → Claude Haiku
Через существующий `core.llm.reply()` с `segment="other", stage="cold"`. История диалога живёт в памяти (последние 10 пар реплик на сессию).

### 4. Новая таблица + миграция
- `whitepaper_leads` (id, email, pdf, source, user_agent, ip_hash, created_at)
- Миграция [`alembic/versions/0008_whitepaper_leads.py`](../edl-os-bot/alembic/versions/0008_whitepaper_leads.py) — применится автоматически на деплое (`preDeployCommand: alembic upgrade head` в railway.json)

### 5. CORS
В `src/main.py` добавлен `CORSMiddleware` с whitelist:
- `https://elephantdreams.ru` (+ www)
- `http://localhost:8000`, `5500`, `127.0.0.1:5500` — для локальной разработки

### 6. Конфигурируемый API_BASE на сайте
- В [`js/bot-widget.js`](../js/bot-widget.js) и [`methodology.html`](../methodology.html) теперь можно переопределить URL бэкенда: добавить перед основным `<script>` строчку:
  ```html
  <script>window.EDL_API_BASE = 'https://edl-site-production.up.railway.app';</script>
  ```
  → если `api.elephantdreams.ru` так и не настроишь, сайт всё равно достучится до Railway напрямую.

---

## Где живёт бот сейчас

Из [`docs/qa_audit_2026-05-17/RAILWAY_WEBHOOK_SETUP.md`](../edl-os-bot/docs/qa_audit_2026-05-17/RAILWAY_WEBHOOK_SETUP.md):

```
https://edl-site-production.up.railway.app
```

Эта же машина теперь раздаёт:
- `/health` — было
- `/webhook` — было (Telegram)
- `/admin/*` — было
- `/widget/message`, `/widget/stream/{id}` — новые
- `/leads/whitepaper` — новый

После мержа PR Railway сам пересоберёт контейнер и применит миграцию 0008.

---

## Что нужно решить про `api.elephantdreams.ru`

`api.elephantdreams.ru` сейчас в DNS не существует (curl выдаёт «Could not resolve host»). Выбери один из трёх вариантов:

### Вариант 1 — без DNS, через Railway URL (рекомендую на сегодня)
**Самый быстрый.** Просто на каждой странице сайта в `<head>` добавить:
```html
<script>window.EDL_API_BASE = 'https://edl-site-production.up.railway.app';</script>
```
Я могу это сделать сейчас — займёт 5 минут. Минусы: URL технический, видно в DevTools; если Railway переименует сервис — поломается. Плюсы: работает завтра без действий с DNS.

### Вариант 2 — добавить CNAME `api.elephantdreams.ru → ...railway.app`
**Чистый продакшен-вариант.** В админке регистратора домена `elephantdreams.ru`:
1. Добавить DNS-запись типа `CNAME` для поддомена `api` → значение `edl-site-production.up.railway.app`
2. В Railway → Settings → Domains → Custom Domain → `api.elephantdreams.ru`
3. Railway сам выпустит TLS-сертификат (минут 10–30)
4. Ничего на сайте править не надо — код уже ходит на `api.elephantdreams.ru`

Когда заработает — проверить:
```bash
curl -i https://api.elephantdreams.ru/health
# должен вернуть {"status":"ok","use_webhook":true,...}
```

### Вариант 3 — кодом ходить на основной домен `elephantdreams.ru/api/*`
**Самый сложный.** Прокинуть прокси через тот же хостинг, что отдаёт статику (`elephantdreams.ru`). Имеет смысл если статика тоже на Railway/Render. Если статика на GitHub Pages/Cloudflare Pages — это лишняя возня.

---

## Чек-лист на 19.05

- [ ] Замержить PR `claude/website-v4-updates` (после твоего ОК)
- [ ] Дождаться, что Railway деплой прошёл (`https://edl-site-production.up.railway.app/health` отвечает + миграция 0008 в логах)
- [ ] Решить про DNS:
  - [ ] Вариант 1 (быстро) → попроси меня вставить `window.EDL_API_BASE = '...'` на страницы
  - [ ] Вариант 2 (чисто) → добавить CNAME у регистратора + custom domain в Railway
- [ ] Проверить виджет: открыть сайт, прокрутить 30%, подождать 30 сек → должен открыться чат, нажать кнопку → должен прийти ответ
- [ ] Проверить whitepaper-форму на methodology.html: ввести email → нажать «Скачать PDF» → должен открыться PDF и прийти TG-уведомление в админ-чат

---

## Что ещё не сделано (на потом)

- **Email-доставка whitepaper PDF**: сейчас форма только сохраняет email и открывает PDF в новой вкладке. Если нужно действительно слать письмо с прикреплённым PDF — подключить Resend/Postmark/SES. Текст шаблона потребуется отдельно.
- **Виджет на мобиле**: открывается на весь экран (100vw/100vh). UX надо прокликать вживую.
- **Персистентность виджет-сессий**: история диалога живёт в памяти контейнера. На перезапуске → теряется. Если важно — добавить отдельную таблицу `widget_messages` (схема готова к этому, надо только написать модель + миграцию).
- **Эскалация на менеджера в нерабочее время**: сейчас при «Связаться с менеджером» алерт улетает в `ADMIN_CHAT_ID` независимо от часа. Можно прикрутить `core/working_hours.py` если хочется отбивать «напишем утром».
