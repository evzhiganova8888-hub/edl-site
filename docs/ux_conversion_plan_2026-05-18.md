# EDL OS · UX/Conversion Plan — 2026-05-18

> **Цель документа.** Передать новому чату весь контекст для реализации UX/конверсионного апгрейда сайта `elephantdreams.ru` до уровня «10/10 за 5 секунд».
> Документ самодостаточный. Не нужно открывать прошлые сессии или summary.
> **Сначала прочитай §0 — Onboarding нового чата.** Потом §1 (TL;DR), потом §3+ по порядку.

---

## 0. Onboarding нового чата

### 0.1 Кто пользователь
**Евгения Жиганова** (Telegram @ekaterina_zhiganova; на сайте «Екатерина» — это бренд-имя). Владелица:
- сайта **elephantdreams.ru** (репо `evzhiganova8888-hub/edl-site`, GitHub Pages)
- Telegram-бота **@edl_os_bot** (код в подкаталоге `edl-os-bot/`, деплой Railway)
- продукта **EDL OS** — Бизнес-чекап (9 000 ₽ Base / 14 000 ₽ Plus), Диагностика (25 000 ₽), Спринт (135 000–260 000 ₽), План Роста (50 000–110 000 ₽/мес)

Работает по-русски. Любит **нон-стоп режим** с явным «ОК» перед деструктивными операциями (мерж, force-push, drop). Деплоит сама через GitHub UI / Railway dashboard.

### 0.2 Где живёт правда
| Источник | Что внутри | Когда использовать |
|---|---|---|
| `edl-os-bot/CLAUDE.md` | source-of-truth по боту: модели, миграции, команды, security | Любая работа с ботом / БД |
| `docs/website_v4_status_2026-05-18.md` | что сделано на сайте в сессии 18.05 (виджет, leads-endpoint, PDF) | Контекст моих параллельных правок |
| `docs/backend_widget_deploy_2026-05-18.md` | бэкенд для виджета + whitepaper-формы | DNS уже настроен, см. §11 |
| `docs/dns_setup_api_subdomain_2026-05-18.md` | как был настроен `api.elephantdreams.ru` → Railway | Работает на 19.05.2026 ✅ |
| `Downloads/EDL_Session_Summary_20260518.md` | параллельная сессия — PR #33, #35 (merged), #36, #37 (draft) | Контекст что уже в main |
| **Этот документ** | UX/конверсионный план — то, что делаем сейчас | План работы |

### 0.3 Параллельные сессии и состояние веток
**ВНИМАНИЕ.** За день 18.05 шли **две параллельные сессии Claude**. Они не знали друг о друге → две разные ветки правят одни и те же файлы (`index.html`, `audit.html`, `methodology.html`, `edl-os-bot/src/main.py`, `edl-os-bot/src/db/models.py`).

| Ветка | Коммит | Статус | Что делает |
|---|---|---|---|
| `main` | `d201225` | актуальная база | PR #33+#35 уже мержены (whitepaper v4 + email-gate + PDF в `/assets/pdf/`) |
| `claude/website-v4-updates` | `2fcabf3` | **конфликтует с main** | моя сессия: leads-endpoint + миграция 0008 → конфликт с `0008_widget_sessions` |
| `claude/site-ux-top-wins` | PR #36 | draft | UX top wins другой сессии |
| `claude/site-ux-polish` | PR #37 | draft | UX polish другой сессии |

**Что делать с моей веткой `claude/website-v4-updates`:**
1. Сначала спросить пользователя — мержить через rebase или закрыть PR без мержа. Большая часть моих изменений (PDF-ссылки, новый виджет) уже сделана параллельной сессией другим способом. Уникально полезное: `POST /leads/whitepaper` endpoint + миграция `0012_whitepaper_leads.py` + `docs/dns_setup_api_subdomain_2026-05-18.md`.
2. Рекомендация: cherry-pick только `src/leads/`, миграцию (перенумеровать в `0012`), и docs. Остальное — закрыть.

### 0.4 Деплой и проверка
- **Сайт**: GitHub Pages, домены `elephantdreams.ru` + `www.elephantdreams.ru`. Деплой автоматом на push в `main`.
- **Бот**: Railway, проект `efficient-appreciation`, сервис `edl-site`. Деплой автоматом на push в `main`. Миграции через `preDeployCommand: alembic upgrade head`.
- **API-домен**: `api.elephantdreams.ru` — CNAME → Railway, TLS активен. Проверка: `curl -i https://api.elephantdreams.ru/health` → 200.
- **GitHub repo**: `https://github.com/evzhiganova8888-hub/edl-site`

### 0.5 Гайдлайны при работе
1. **Не править файлы без чтения сначала.** Тулза `Edit` блокирует это.
2. **Russian-first** в коммуникации и комментариях в коде на сайте. Код-комментарии в боте — можно English/Russian.
3. **Сначала спрашивать перед деструктивными операциями**: force-push, rebase, удаление веток, миграции с DROP.
4. **Миграции — только аддитивные** (CREATE TABLE, ADD COLUMN NULLABLE).
5. **Один PR = одна тема.** Не смешивать UX-правки с бэкенд-фиксами.
6. **Не дублировать.** Перед добавлением виджет-эндпоинта или модели проверить `git show origin/main:edl-os-bot/src/main.py` и `models.py` — параллельная сессия могла уже это сделать.

---

## 1. TL;DR — главное за 60 секунд

**Проблема, которую нужно решить.** Фидбэк ревьюера (см. скрины в чате 18.05):
> «Нет узнавания с первого взгляда что вы конкретно делаете. Нужны картинки хотя бы.»
> «Ничо не понятно, я б денег не дал. Даже вникать не стал бы.»
> «Нужна формулировка проблемы, которую решит система. Одной строкой.»

**Эталон, на который равняемся** (тоже из фидбэка):
- **amoCRM** — H1 «Не теряйте клиентов». Одна боль, один глагол, считывается за 1 секунду.
- **Brizo** — «CRM с финансово-управленческим учётом → автоматизирует процессы, наведёт порядок в финансах, увеличит продажи, покажет реальную прибыль». Формулировка + 4 конкретных результата.

**Главный фикс.** Hero на `index.html`. Сейчас H1 = «Бортовой компьютер для бизнеса 10–50 человек. Операционная система собственника нового поколения.» Это **метафора**, а не боль. Заменяем на **гибрид боль+результат**:

> # Видеть, где утекает маржа вашего бизнеса — ежедневно, а не раз в квартал.
>
> • Каждый клиент в плюсе или в минусе — видно сразу
> • НДС 2026 посчитан и подсвечен в PDF через 24ч
> • Сводка в Telegram каждое утро

Плюс заменить пустой Telegram-мокап справа на **GIF/видео-демо** реального продукта.

**Объём работы.** Полный аудит ключевых страниц: `index.html` + `audit.html` + `methodology.html` (подробно). Остальные (`pricing.html`, `faq.html`, `cases.html`, `about.html`) — чеклистом. Оценка: 1.5–2 дня + запись GIF/видео (внешняя задача).

**8 блокеров → 8 итераций** (см. §3).

---

## 2. Состояние сайта на 2026-05-18 (актуально)

### 2.1 Структура страниц
| URL | Файл | Назначение | Что задеплоено |
|---|---|---|---|
| `/` | `index.html` | Главная | H1 «Бортовой компьютер», ICP-свитчер, лестница продуктов, кейсы, FAQ |
| `/audit.html` | Бизнес-чекап (9 000 ₽ Base / 14 000 ₽ Plus), Telegram-flow, оплата, гарантия | Email-gate для whitepaper в FAQ |
| `/methodology.html` | Founder OS методология, 3 слепых пятна, синтез | Email-gate форма (PDF только по email) |
| `/pricing.html` | Лестница из 5 продуктов | Founder OS Score, Бизнес-чекап Base/Plus, Диагностика, Спринт, План Роста |
| `/faq.html` | 17 вопросов, в drafts (PR #37) — пересортированы в 5 секций | Команды бота, гарантии, безопасность |
| `/cases.html` | Кейсы | Сейчас — `case-soon` placeholders с email-формой |
| `/about.html` | Команда | Катя, метод, миссия |
| `/try-in-claude.html` | MCP Claude Desktop / Cursor | Запуск 23.05.2026 |
| `/legal/*` | Оферта, политика, оферта-чекап | Юридическая база |

### 2.2 PDF-файлы (canonical)
| Что | Путь | Размер |
|---|---|---|
| Whitepaper «Founder OS» v4 | `assets/pdf/edl-founder-os-whitepaper.pdf` | 82 КБ |
| Product Ladder | `assets/pdf/edl-product-ladder.pdf` | 2,5 МБ |
| HTML-source whitepaper | `assets/pdf/founder-os-whitepaper/whitepaper.html` | — |

⚠️ Старые ссылки `/assets/pdf/edl-founder-os-v1.pdf` и `/assets/EDL_*.pdf` **больше не существуют**. На прошлой ветке у меня были на них ссылки — это устарело, см. §0.3.

### 2.3 Бэкенд эндпоинты
| Эндпоинт | Что делает | Где определено |
|---|---|---|
| `GET /health` | Liveness | `edl-os-bot/src/main.py` |
| `POST /webhook` | Telegram updates | `edl-os-bot/src/main.py` |
| `POST /widget/message` | Веб-виджет → бот | `edl-os-bot/src/main.py` (от параллельной сессии — префикс `widget_`) |
| `GET /widget/stream/{session_id}` | SSE ответы | `edl-os-bot/src/main.py` |
| `POST /leads/whitepaper` | **Не в main.** В моей ветке `claude/website-v4-updates` — `src/leads/routes.py` | Нужен cherry-pick |
| `POST /leads/case-notify` | **Не сделан.** Описан в session summary PR #37 | TODO |
| `GET /admin/*` | Админ-API | `edl-os-bot/src/admin/routes.py` |

### 2.4 Связь сайта и бота
1. **Кнопки «Бизнес-чекап 9 000 ₽» → @edl_os_bot?start=audit** (deep-link)
2. **Кнопки «Founder OS Score»** — в hero открывают **Mini-Чекап modal** (`js/mini-checkup.js`), внутри сайта без перехода в TG
3. **Bot-widget bubble** в правом нижнем углу — `js/bot-widget.js`, использует `widget_xxx` session-id, ходит на `api.elephantdreams.ru/widget/*`
4. **Email-gate whitepaper** — `methodology.html` шлёт `POST /leads/whitepaper` (но endpoint ещё не задеплоен, см. §11)
5. **Лидов на Диагностику/Спринт** — через `@edl_os_bot?start=diagnostic`, `?start=sprint_waitlist`

---

## 3. 8 блокеров узнавания — диагноз

Все блокеры — на главной (`index.html`). Сортировка по силе влияния на конверсию (P1 → P3).

| # | Блокер | Симптом у ревьюера | Где | Приоритет |
|---|---|---|---|---|
| 1 | **H1 = метафора, а не боль.** «Бортовой компьютер / ОС собственника нового поколения» | «Нет узнавания с первого взгляда» | `index.html:152` | P1 |
| 2 | **Subtitle перегружен 3 фичами** «Сводка + ИИ + без дашбордов + без паролей + без IT» | Глаз не успевает зацепиться, ничего не запоминается | `index.html:153` | P1 |
| 3 | **Hero-визуал пустой** — справа `tg-window__idle` с надписью «📡 Выберите нишу выше» | «Нужны картинки хотя бы» — буквально про это | `index.html:184–193` | P1 |
| 4 | **Два равнозначных CTA** «Score · 12 вопросов» + «Бизнес-чекап 9 000 ₽» одинаково ярких | Paradox of choice, конверсия размывается на оба | `index.html:158–168` | P2 |
| 5 | **Trust-strip с эмодзи** «🛡 Open source · 🔌 1С · 🇷🇺 Геткурс» вместо реальных лого | Не выглядит как продакшен-продукт | `index.html:170–176` | P2 |
| 6 | **Нет «proof-of-product» ниже hero**: ни скриншота PDF, ни фото Кати, ни «было/стало», ни лого клиентов (даже анонимных вертикалей) | Дальше по странице — текст-текст-текст | весь `index.html` | P1 |
| 7 | **Имя «EDL OS» нерасшифровано** — бренд или аббревиатура? | Лишний барьер при первом контакте | везде | P3 |
| 8 | **Pricing-блок на главной** показывает 5 продуктов до того, как продано «зачем» | Преждевременная цена | `index.html` (после кейсов) | P3 |

---

## 4. Hero (index.html) — главный фикс

### 4.1 Текущее состояние

**Файл**: `index.html`
**Строки**: ~141–230 (вся секция `<section class="hero">`)

```html
<h1 class="hero__title" style="font-size: clamp(2rem, 5vw, 3.5rem); line-height: 1.1; margin-bottom: 24px;">
  Бортовой компьютер для бизнеса
  <span style="color:var(--color-tangerine); white-space:nowrap;">10–50 человек.</span>
  <br>
  <span style="color:var(--color-tangerine)">Операционная система собственника нового поколения.</span>
</h1>
<p class="hero__subtitle">
  Все цифры, риски и решения вашего бизнеса — в одном месте.
  Утренняя сводка в Telegram + ИИ-консультант под рукой.
  Без дашбордов, без новых паролей, без IT-отдела.
</p>
<div class="hero__badge">Работает в Telegram · Бизнес-чекап за 24 часа · Все данные остаются у вас</div>
```

Справа — пустой ICP-свитчер и `<div class="tg-window__idle">📡 Выберите нишу выше...</div>`.

### 4.2 Целевой H1 + subtitle (СОГЛАСОВАНО)

**Замени `index.html:151–155` на:**

```html
<h1 class="hero__title" style="font-size: clamp(2rem, 5vw, 3.5rem); line-height: 1.1; margin-bottom: 20px;">
  Видеть, где утекает маржа вашего бизнеса —
  <span style="color: var(--color-tangerine);">ежедневно, а не раз в квартал.</span>
</h1>

<ul class="hero__bullets" style="list-style:none; padding:0; margin:0 0 32px; display:flex; flex-direction:column; gap:10px;">
  <li style="display:flex; gap:10px; align-items:flex-start; font-size:1.0625rem; color: var(--color-gray-800); line-height:1.45;">
    <span style="color: var(--color-tangerine); font-weight:700; flex-shrink:0;">▸</span>
    <span>Каждый клиент в плюсе или в минусе — <strong>видно сразу</strong></span>
  </li>
  <li style="display:flex; gap:10px; align-items:flex-start; font-size:1.0625rem; color: var(--color-gray-800); line-height:1.45;">
    <span style="color: var(--color-tangerine); font-weight:700; flex-shrink:0;">▸</span>
    <span>НДС 2026 посчитан и подсвечен в PDF — <strong>через 24 часа</strong></span>
  </li>
  <li style="display:flex; gap:10px; align-items:flex-start; font-size:1.0625rem; color: var(--color-gray-800); line-height:1.45;">
    <span style="color: var(--color-tangerine); font-weight:700; flex-shrink:0;">▸</span>
    <span>Сводка по бизнесу в Telegram — <strong>каждое утро</strong></span>
  </li>
</ul>
```

**Принципы:**
- Глагол первым, конкретный («видеть», а не «получите доступ к»)
- «Маржа» — общеупотребимая боль для собственника 10-50 (в отличие от «оптимизации процессов»)
- Контраст «ежедневно / раз в квартал» — поясняет, в чём отличие от текущей жизни
- 3 буллета = 3 конкретных результата (как в Brizo), но короче — каждый ≤8 слов
- **strong** на результате, а не на действии — глаз падает на «видно сразу / через 24 часа / каждое утро»

### 4.3 Hero-визуал: GIF/видео-демо (СОГЛАСОВАНО)

Сейчас справа — пустой Telegram-мокап до взаимодействия. Меняем на **15-секундный GIF/MP4-демо** с автоплеем без звука.

**Спецификация GIF/MP4 (внешняя задача — записать вне кода):**

| Параметр | Значение |
|---|---|
| Длительность | 12–15 секунд (loop) |
| Размер | 600×900 px (вертикальный, мокап телефона) |
| Формат | MP4 (h264, low bitrate) + WebM fallback; статичный poster PNG для медленного интернета |
| Размер файла | ≤ 800 КБ |
| Звук | без звука |
| Autoplay | да + loop + muted (всё в `<video>` атрибутах) |
| Reduced motion | для `prefers-reduced-motion: reduce` — отдать статичный PNG |

**Сценарий 12 секунд** (timeline для записи):
1. **0–1 сек**: на экране телефона видна заглавная страница чата с `@edl_os_bot`. Заголовок «утренняя сводка 19 мая».
2. **1–4 сек**: набираются по очереди 3 пузыря из бота:
   - «📊 Маржа по проектам мая: **-2.1 п.п.** Убыточные клиенты: 3 из 24»
   - «🔥 HOT-сделки без касания > 24ч: Петров (1.2М), ООО Стройбаза (800k)»
   - «💰 НДС 2026 по последним 5 контрактам: +180 000 ₽ к плану. Карта в PDF»
3. **4–6 сек**: пользователь печатает: «А какой самый убыточный клиент?»
4. **6–9 сек**: бот печатает: «Клиент Z — маржа -8% при среднем 18%. Главная причина: 2 правки в работе...»
5. **9–11 сек**: пользователь жмёт inline-кнопку «Открыть PDF-чекап» → экран сменяется на превью PDF (НДС-карта)
6. **11–12 сек**: затемнение + текст overlay «EDL OS · 24 часа на полную картину»

**Где взять контент для GIF**:
- скриншоты — из `assets/audit_sample.html` (пример отчёта Чекапа из бота)
- макет бот-сводки — из `index.html:178–227` (templates `tpl-services`, `tpl-manufacturing` и т.д.)
- НДС-карта — из whitepaper стр. 5 (там есть сравнительная таблица)

**HTML-замена `index.html:181–230` (вся секция `<div class="hero__demo">`):**

```html
<!-- Right Side: Hero demo video (12-second loop) -->
<div class="hero__demo">
  <div class="hero-demo-frame" style="position:relative; max-width:380px; margin:0 auto;">
    <video
      class="hero-demo-video"
      autoplay
      muted
      loop
      playsinline
      poster="/assets/hero-demo-poster.jpg"
      aria-label="EDL OS — пример утренней сводки в Telegram и PDF-чекапа"
      style="width:100%; height:auto; border-radius:24px; box-shadow:0 20px 50px rgba(0,0,0,0.15); display:block;"
    >
      <source src="/assets/hero-demo.mp4" type="video/mp4">
      <source src="/assets/hero-demo.webm" type="video/webm">
      <!-- Fallback для браузеров без видео -->
      <img src="/assets/hero-demo-poster.jpg" alt="EDL OS — утренняя сводка в Telegram" style="width:100%; border-radius:24px;">
    </video>
    <div class="hero-demo-caption" style="text-align:center; margin-top:14px; font-size:0.875rem; color:var(--color-gray-700);">
      Так выглядит работа собственника <strong>через 14 дней</strong> после Бизнес-чекапа
    </div>
  </div>
</div>
```

**Reduced motion (добавь в `css/main-v2.css`):**

```css
@media (prefers-reduced-motion: reduce) {
  .hero-demo-video { display: none; }
  .hero-demo-frame::before {
    content: '';
    display: block;
    width: 100%;
    aspect-ratio: 2 / 3;
    background: url('/assets/hero-demo-poster.jpg') center/cover no-repeat;
    border-radius: 24px;
    box-shadow: 0 20px 50px rgba(0,0,0,0.15);
  }
}
```

**ICP-свитчер** (`index.html:182–188`) — **переносим вниз** в отдельную секцию «Покажите для моей ниши» (см. §6). Свитчер — это интерактивный proof, но не дефолт для hero. Гость, который зашёл с мобильника на 5 секунд, не успевает понять, что нужно нажимать кнопки.

### 4.4 Один primary CTA (фикс P2 блокера #4)

**Текущее состояние (`index.html:158–168`):** две кнопки одного веса:
1. «💬 Founder OS Score · 12 вопросов» (primary tangerine button)
2. «Бизнес-чекап 9 000 ₽ →» (outline button)

**Решение**: primary один — **Бизнес-чекап**. Score уходит в secondary (текстовая ссылка под CTA).

```html
<div style="display:flex; gap:16px; margin-top:24px; flex-wrap:wrap; align-items:center;">
  <a href="audit.html" class="btn btn--primary" style="font-size:1.0625rem; padding:14px 28px;" data-cta-type="audit" data-cta-location="hero">
    Получить чекап за 9 000 ₽ →
  </a>
  <button type="button" class="hero__secondary-cta" data-mc-open="hero" style="background:none; border:none; color:var(--color-tangerine); font-weight:600; cursor:pointer; text-decoration:underline; font-size:0.9375rem;">
    Или попробуйте Founder OS Score бесплатно (15 мин)
  </button>
</div>
```

**Почему так**: главная цель сайта в мае — конверсия в **платный чекап** (по бизнес-плану Кати). Score — это lead-magnet для тех, кто не готов платить. Делая Score primary, мы каннибализируем платную конверсию.

### 4.5 Trust-strip → 3 реальных лого + бейдж безопасности (фикс P2 блокера #5)

Сейчас (`index.html:170–176`):

```html
<div class="trust-strip" role="list">
  <span class="trust-strip__badge">🛡 Open source MCP</span>
  <span class="trust-strip__sep">·</span>
  <span class="trust-strip__badge">🔌 1С · amoCRM · Битрикс</span>
  <span class="trust-strip__sep">·</span>
  <span class="trust-strip__badge">🇷🇺 Геткурс · Тинькофф · (доступны на этапе Диагностики)</span>
</div>
```

**Замена** (логотипы вместо эмодзи — нужны SVG в `/assets/logos/`):

```html
<div class="trust-strip" role="list" style="display:flex; gap:24px; align-items:center; flex-wrap:wrap; margin-top:24px; opacity:0.75;">
  <span style="font-size:0.8125rem; color:var(--color-gray-600); font-weight:500;">Интеграции:</span>
  <img src="/assets/logos/1c.svg"      alt="1С"        style="height:24px; filter:grayscale(1);">
  <img src="/assets/logos/amocrm.svg"  alt="amoCRM"    style="height:24px; filter:grayscale(1);">
  <img src="/assets/logos/bitrix.svg"  alt="Битрикс24" style="height:24px; filter:grayscale(1);">
  <img src="/assets/logos/tinkoff.svg" alt="Тинькофф"  style="height:24px; filter:grayscale(1);">
  <img src="/assets/logos/getcourse.svg" alt="GetCourse" style="height:24px; filter:grayscale(1);">
</div>
<div style="margin-top:12px; font-size:0.8125rem; color:var(--color-gray-500);">
  152-ФЗ: <strong>все данные на вашей инфраструктуре</strong> · Возврат 14 дней без причины · Open source MCP-сервер
</div>
```

**Где взять лого:**
- 1С: <https://1c.ru/news/info.jsp?id=24180> (есть press-kit)
- amoCRM: <https://www.amocrm.ru/brand/>
- Битрикс24: <https://www.bitrix24.ru/about/press/>
- Тинькофф: <https://www.tinkoff.ru/about/media-center/>
- GetCourse: <https://getcourse.ru/brand>

Альтернатива — нарисовать generic wordmark на каждый бренд в Figma (один шрифт Inter Bold) — займёт 30 мин на все 5.

### 4.6 Точные правки в файле — sequence

```text
1. Read index.html, найти секцию hero (~141–230)
2. Edit hero__title (строка ~152) — заменить H1
3. Edit hero__subtitle (строка ~153) — заменить на <ul class="hero__bullets">
4. Edit hero__badge (~154) — удалить, бейдж уйдёт под CTA
5. Edit блок кнопок (~158–168) — оставить одну primary + secondary текст
6. Edit trust-strip (~170–176) — заменить на лого
7. Edit hero__demo (~181–230) — целиком заменить на <video>
8. Edit hero__cta-note (~177) — оставить как есть, это про возврат
9. Удалить tg-window templates (~213–226) — теперь не нужны
10. Удалить связанные JS-обработчики в js/main.js — поиск 'tg-trigger', 'tg-restart', 'icp-switcher'
```

**Что НЕ удалять:**
- `Mini-Чекап modal` (js/mini-checkup.js) — он работает на странице, secondary CTA в hero его открывает
- `bot-widget.js` — нижний bubble виджет

---

## 5. Секция «У вас так?» (новый блок после hero)

Между hero и текущим блоком «Проблема, для которой решение» вставить новый разделитель — **диагностику от первого лица**.

**Цель**: посетитель кивает «да, у меня так» → доверие к продукту через мостик «они меня понимают».

**Файл**: `index.html`, после закрывающего `</section>` hero (~230).

```html
<!-- Section: «У вас так?» — резонанс боли -->
<section class="section section--gray" style="padding: 80px 0;">
  <div class="container" style="max-width:920px;">
    <h2 class="section__title" style="text-align:center; margin-bottom:48px;">У вас так?</h2>
    <div class="pain-grid" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:24px;">
      <div class="pain-card" style="background:#fff; padding:28px 24px; border-radius:16px; border:1px solid var(--color-gray-200);">
        <div style="font-size:2rem; margin-bottom:12px;" aria-hidden="true">📊</div>
        <h3 style="font-weight:600; margin-bottom:8px; font-size:1.125rem;">Бухгалтерия раз в месяц, факты раз в квартал</h3>
        <p style="color:var(--color-gray-700); font-size:0.9375rem; line-height:1.5;">К моменту, когда видно убыточный контракт, он уже съел маржу полугодия.</p>
      </div>
      <div class="pain-card" style="background:#fff; padding:28px 24px; border-radius:16px; border:1px solid var(--color-gray-200);">
        <div style="font-size:2rem; margin-bottom:12px;" aria-hidden="true">🌪️</div>
        <h3 style="font-weight:600; margin-bottom:8px; font-size:1.125rem;">Стратегия живёт в голове основателя</h3>
        <p style="color:var(--color-gray-700); font-size:0.9375rem; line-height:1.5;">Команда выросла, но непонятно — куда. Решения принимаются интуитивно.</p>
      </div>
      <div class="pain-card" style="background:#fff; padding:28px 24px; border-radius:16px; border:1px solid var(--color-gray-200);">
        <div style="font-size:2rem; margin-bottom:12px;" aria-hidden="true">⚖️</div>
        <h3 style="font-weight:600; margin-bottom:8px; font-size:1.125rem;">НДС 2026: знаете формулу, но не последствия</h3>
        <p style="color:var(--color-gray-700); font-size:0.9375rem; line-height:1.5;">Не понятно, какие из ваших контрактов окажутся под лимитом УСН.</p>
      </div>
      <div class="pain-card" style="background:#fff; padding:28px 24px; border-radius:16px; border:1px solid var(--color-gray-200);">
        <div style="font-size:2rem; margin-bottom:12px;" aria-hidden="true">🤖</div>
        <h3 style="font-weight:600; margin-bottom:8px; font-size:1.125rem;">ИИ хочется, но непонятно куда</h3>
        <p style="color:var(--color-gray-700); font-size:0.9375rem; line-height:1.5;">Где он реально даст пользу, а где будет имитировать работу — без рамки выбора непонятно.</p>
      </div>
    </div>
    <div style="text-align:center; margin-top:40px;">
      <p style="color:var(--color-gray-700); margin-bottom:16px; font-size:1.125rem;">EDL OS закрывает все четыре пункта за один Бизнес-чекап.</p>
      <a href="audit.html" class="btn btn--primary" data-cta-type="audit" data-cta-location="pain_section">Заказать чекап за 9 000 ₽ →</a>
    </div>
  </div>
</section>
```

---

## 6. Секция «Что получите» — переработка с визуалом

Текущая секция «Бортовой компьютер собирается за 4 недели» в `index.html` (поиск `class="value-grid"` или похожее) — оставить, но **добавить визуал к каждому пункту**.

**Каждая карточка должна иметь:** иконку → заголовок → 1 строка описания → **скриншот**.

| Карточка | Заголовок | Скриншот |
|---|---|---|
| 1 | **PDF-чекап за 24 часа** | Превью первой страницы `audit_sample.html` (отрендерить в PNG) |
| 2 | **Утренняя сводка в Telegram** | Скриншот реального TG-чата с ботом |
| 3 | **ИИ-консультант под рукой** | Скриншот вопроса-ответа в @edl_os_bot |
| 4 | **НДС-карта 2026** | Фрагмент таблицы из whitepaper стр. 5 |

**Где взять скриншоты:**
- PDF — открыть `assets/audit_sample.html` в Chrome → Print → Save as PNG → обрезать в Figma до 400×600
- TG-сводка — скриншот реального бота, замазать персональные данные
- НДС-карта — открыть `assets/pdf/founder-os-whitepaper/whitepaper.html` → скрин страницы 5

Все скрины положить в `assets/screenshots/`:
- `audit-pdf-preview.png` (400×600)
- `tg-morning-summary.png` (400×600)
- `tg-ai-consultant.png` (400×600)
- `vat-map-2026.png` (400×600)

---

## 7. ICP-свитчер — вернуть, но в отдельной секции

ICP-свитчер с примерами сводок (`index.html:182–227`) — это сильный proof-of-product, его не нужно убирать насовсем. Только **переносим из hero вниз**, в свою секцию после «Что получите».

```html
<section class="section" id="icp-demo" style="padding: 80px 0;">
  <div class="container" style="max-width:880px;">
    <h2 class="section__title" style="text-align:center;">Покажите, как EDL OS работает в моей нише</h2>
    <p style="text-align:center; color:var(--color-gray-700); margin-bottom:40px;">Выберите ваш сегмент бизнеса — увидите реальный пример сводки.</p>
    <!-- Сюда переносим icp-switcher и tg-window из текущего hero -->
  </div>
</section>
```

После переноса: вернуть ICP-кнопки + дефолтное состояние **сразу залить контентом «Услуги»** (не «📡 Выберите нишу»).

---

## 8. Кейсы — заменить placeholders на 1 реальный кейс

Сейчас `cases.html` и блок кейсов на `index.html` показывают `case-soon` placeholders с email-формой «получите уведомление о публикации кейса». Это **трижды плохо**:
- посетитель видит, что кейсов нет → ставит под сомнение, что продукт работает
- email-форма требует действия без ценности взамен
- ширит технический долг (`/leads/case-notify` endpoint ещё не сделан)

**Решение:** для мая — **1 анонимный кейс с реальными цифрами**.

VITACONSULT_PUBLIC = false до 22.05.2026 (NDA), но можно сделать **анонимный кейс «Услуги · b2b · 35 сотрудников»** без названия компании.

**Структура кейса** (`index.html` → блок кейсов или `cases.html`):

```html
<article class="case-card" style="background:#fff; padding:32px; border-radius:20px; border:1px solid var(--color-gray-200); max-width:720px; margin:0 auto;">
  <div style="display:flex; gap:16px; align-items:center; margin-bottom:24px;">
    <div style="width:64px; height:64px; background:var(--color-tangerine-light); border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:1.75rem;" aria-hidden="true">🏢</div>
    <div>
      <div style="font-weight:700; font-size:1.125rem;">B2B-услуги · 35 сотрудников</div>
      <div style="font-size:0.875rem; color:var(--color-gray-600);">Внедрение EDL OS · 4 недели</div>
    </div>
  </div>
  <h3 style="font-size:1.375rem; margin-bottom:16px;">«Узнали, что 3 из 24 клиентов работают в минус. Перезаключили — маржа +4 п.п. за квартал.»</h3>
  <div class="case-stats" style="display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin:24px 0;">
    <div style="text-align:center; padding:16px; background:var(--color-gray-50); border-radius:12px;">
      <div style="font-size:2rem; font-weight:700; color:var(--color-tangerine);">3 из 24</div>
      <div style="font-size:0.875rem; color:var(--color-gray-600);">убыточных контрактов нашли</div>
    </div>
    <div style="text-align:center; padding:16px; background:var(--color-gray-50); border-radius:12px;">
      <div style="font-size:2rem; font-weight:700; color:var(--color-tangerine);">+4 п.п.</div>
      <div style="font-size:0.875rem; color:var(--color-gray-600);">маржа за квартал</div>
    </div>
    <div style="text-align:center; padding:16px; background:var(--color-gray-50); border-radius:12px;">
      <div style="font-size:2rem; font-weight:700; color:var(--color-tangerine);">28 дней</div>
      <div style="font-size:0.875rem; color:var(--color-gray-600);">до первых результатов</div>
    </div>
  </div>
  <p style="color:var(--color-gray-700); line-height:1.6;">До: ручные отчёты в Excel раз в квартал, маржа считалась по компании в целом. После: <strong>каждое утро сводка в Telegram</strong> с проблемными клиентами + PDF-разбор по 4 слоям с НДС-картой 2026. Команда не выросла. ИТ-внедрений не было.</p>
  <div style="margin-top:24px; padding-top:24px; border-top:1px solid var(--color-gray-200); font-size:0.875rem; color:var(--color-gray-600); font-style:italic;">
    NDA — название компании раскроем после 22.05.2026. Цифры подтверждены реальной отчётностью.
  </div>
</article>
```

**После 22.05.2026** — заменить «B2B-услуги · 35 сотрудников» на реальное имя клиента + добавить фото лица CFO (с разрешения).

---

## 9. audit.html — апдейт

Audit-страница в целом хорошая — продаёт чекап, есть Plus-апсейл, гарантия, FAQ. **Не ломаем**, добавляем точечные правки.

### 9.1 Hero audit-страницы — добавить визуал

Сейчас:
```html
<h1>Бизнес-чекап за 9 000 ₽.</h1>
<h2>Карта вашего бизнеса за 1-2 часа в боте + 24ч обработки.</h2>
<div class="video-placeholder">🎥 Снимаем 23 мая, обновим на этой странице</div>
```

**Замена на готовое видео** (когда снимется 23.05) — 30–60 секунд:
- Катя у камеры, 15 сек: «Привет, я Катя. Я делаю Бизнес-чекап для бизнесов 10-50 человек...»
- 15 сек экран-кэст: показывает PDF-отчёт с НДС-картой и пометками
- 10 сек: «За 9 000 ₽ и 24 часа вы узнаете 3 главные точки роста. Деньги возвращаются без вопросов.»

Спецификация:
- MP4 h264, 1280×720, ≤8 МБ
- Английские субтитры в `.vtt` файле для accessibility
- Poster: первый кадр Кати в кадре

**До съёмки** — заменить placeholder на статичный коллаж:
- Слева — фото Кати (квадрат 300×300)
- Справа — превью первой страницы PDF (300×400)
- Подпись: «Видео с обзором — 23 мая, после съёмки в студии»

### 9.2 «Что получите» — добавить картинки

Уже есть bundle-grid с 4 пунктами (вопросы в боте / PDF / Майнд-карта / разбор), но без визуала. Добавить иконки 64×64 или мини-скриншоты к каждому.

### 9.3 Plus-апсейл — выделить визуально

Сейчас Plus (14 000 ₽) и Base (9 000 ₽) — почти одинаковые карточки. Plus должен:
- иметь бейдж «★ Самый популярный» (как в pricing-странице после PR #36)
- иметь акцент-цвет на цене (tangerine vs gray)
- иметь видео-превью Кати в превью карточки (60×60 thumbnail с play-иконкой)

---

## 10. methodology.html — апдейт

Methodology — самая «академическая» страница. Тут не нужно «5 секунд» — сюда приходят за глубиной. Но текущие слабые места:

### 10.1 Слепые пятна — добавить визуал к каждому
Сейчас 3 блока «Слепое пятно 01 / 02 / 03» — текст-текст-текст. Добавить:
- Для блока 01 «Не вижу куда уплывает маржа» — мини-диаграмма «маржа по клиентам» (4 столбика, 1 красный)
- Для блока 02 «Нет времени думать стратегически» — иконка горения (стопка задач горит)
- Для блока 03 «Граница с ИИ» — диаграмма Венна «человек / AI / совместно»

Все SVG inline, не картинки — это академический раздел, тут можно «как в whitepaper».

### 10.2 Email-gate форма — улучшить success-state

Сейчас успешная отправка показывает только «Проверьте почту ✓» на кнопке. Заменить на полноценный success-block:

```html
<div id="whitepaper-success" hidden style="background:#10B981; color:#fff; padding:24px; border-radius:12px; margin-top:24px;">
  <div style="display:flex; gap:12px; align-items:center; margin-bottom:8px;">
    <span style="font-size:1.5rem;">✓</span>
    <strong style="font-size:1.125rem;">PDF отправлен на ваш email</strong>
  </div>
  <p style="font-size:0.9375rem; opacity:0.95;">Если не пришло за 5 минут — проверьте спам или напишите на <a href="mailto:hello@edl-os.ru" style="color:#fff; text-decoration:underline;">hello@edl-os.ru</a>.</p>
</div>
```

---

## 11. Бэкенд для лидов (зависимость)

Email-gate на `methodology.html` шлёт `POST /leads/whitepaper` с `{email, source, pdf}`. **Эндпоинт ещё НЕ задеплоен на main.**

В моей ветке `claude/website-v4-updates` (коммит `2fcabf3`) есть готовый код:
- `edl-os-bot/src/leads/__init__.py`
- `edl-os-bot/src/leads/routes.py` — endpoint с rate-limit, валидацией email, записью в БД, нотификацией в `ADMIN_CHAT_ID`
- `edl-os-bot/alembic/versions/0008_whitepaper_leads.py` (нужно перенумеровать в `0012_whitepaper_leads.py` — head на main = `0011_plus_video_fields`)

**Что нужно сделать** (новая ветка `claude/leads-endpoint`):

1. `git checkout main && git pull && git checkout -b claude/leads-endpoint`
2. Cherry-pick без конфликтов:
   ```bash
   git checkout claude/website-v4-updates -- edl-os-bot/src/leads/
   ```
3. Создать миграцию `0012_whitepaper_leads.py` (с `down_revision = "0011_plus_video_fields"`)
4. Добавить модель `WhitepaperLead` в `edl-os-bot/src/db/models.py` (после `WidgetSession`)
5. В `edl-os-bot/src/main.py`:
   ```python
   from src.leads.routes import router as leads_router
   ...
   api.include_router(leads_router)
   ```
6. Добавить CORS если ещё нет (на main уже есть `CORSMiddleware` для виджета)
7. PR → Кате на ревью → merge → Railway применит миграцию

**Endpoint спецификация:**
```http
POST https://api.elephantdreams.ru/leads/whitepaper
Content-Type: application/json

{"email": "user@example.ru", "source": "methodology_page_pdf", "pdf": "founder_os_whitepaper"}

→ 200 OK
{"status": "ok", "download_url": "/assets/pdf/edl-founder-os-whitepaper.pdf"}
```

**Что делает endpoint:**
1. Валидирует email regex
2. Rate-limit: 3 заявки/IP/мин
3. Сохраняет в таблицу `whitepaper_leads` (email + pdf + source + ip_hash + ts)
4. Шлёт в `ADMIN_CHAT_ID` нотификацию «📄 Новый лид: user@example.ru»
5. Возвращает download_url

**Что ОТСУТСТВУЕТ и нужно докрутить отдельно (P2):**
- Реальная email-доставка PDF. Сейчас endpoint только сохраняет email и возвращает URL для скачивания. Чтобы выполнять обещание «PDF отправлен на email» — нужно подключить SMTP (Yandex 360 или transactional service вроде Resend). См. `EDL_Session_Summary_20260518.md` §5.

### 11.1 Также — `POST /leads/case-notify`

PR #37 (draft) добавил email-форму «уведомить о публикации кейса» на `cases.html`. Endpoint **не сделан**. После того как сделаем 1 анонимный кейс (см. §8) — placeholder с email-формой удалится, и эндпоинт не понадобится. Не делать.

---

## 12. Остальные страницы — чеклист

### 12.1 `pricing.html`
- ✅ Лестница из 5 продуктов уже в норме (PR #36 переписал её)
- ⬜ Добавить иконки 64×64 к каждому продукту слева от заголовка
- ⬜ Под лестницей — короткая FAQ-карусель с 3 ключевыми вопросами («Что если не подойдёт?», «Можно остановиться?», «Где гарантия?»)

### 12.2 `faq.html`
- ✅ Уже в drafts (PR #37) — 17 вопросов в 5 секций с jump-nav
- ⬜ После мержа PR #37 — проверить, что все ссылки внутрь работают (`#products`, `#guarantees`, и т.д.)
- ⬜ Добавить в конце «Не нашли ответ? Напишите в чат внизу справа» с открытием bot-widget

### 12.3 `cases.html`
- ⬜ Убрать `case-soon` placeholders с email-формой
- ⬜ Добавить 1 анонимный кейс (см. §8)
- ⬜ Под кейсом — «Скоро публикуем ещё. Подпишитесь на канал» → ссылка на t.me/edl_os (не email-форма)

### 12.4 `about.html`
- ⬜ Hero: фото Кати 400×400 + цитата от первого лица (1 абзац, что она делает и зачем)
- ⬜ Добавить раздел «Кто ещё в команде» — даже если это 1 продуктолог и 1 аналитик, лица + имена + ссылки на LinkedIn
- ⬜ Раздел «Где про нас писали» (если есть медиа-упоминания)

### 12.5 `try-in-claude.html`
- ✅ После PR #37 — code-block с горизонтальным скроллом, готово
- ⬜ Запуск 23.05.2026 — после релиза заменить «скоро» на «доступно сейчас» по всему сайту

### 12.6 `index.html` — финальный CTA-блок (футер)
Сейчас в конце страницы есть «Готовы попробовать?» Проверить:
- ⬜ Один primary CTA (Бизнес-чекап) + один secondary (Score)
- ⬜ Под CTA — line «Возврат 14 дней без причины» + «Без подписок и автосписаний»

---

## 13. Связи и зависимости

### 13.1 Что зависит от чего
```
GIF/видео-демо (внешняя задача — съёмка/Figma)
    ↓
Hero update (§4)
    ↓
Pain section (§5)            ←──┐
    ↓                            │
What you get (§6)               │ (могут идти параллельно)
    ↓                            │
ICP demo restored (§7)       ←──┘
    ↓
Real anonymous case (§8) ← после съёмки и согласования с клиентом
    ↓
audit.html visual (§9) ← после съёмки видео Кати 23.05
    ↓
methodology.html visuals (§10)
    ↓
Other pages checklist (§12)
```

### 13.2 Параллельно с UX (бэкенд + почта)
- `POST /leads/whitepaper` — отдельная задача (§11), не блокирует UX
- Yandex 360 SMTP для email-доставки PDF — внешняя задача (`EDL_Session_Summary_20260518.md` §5)

### 13.3 Внешние ресурсы (для съёмки/Figma)
- Студия для съёмки видео Кати — 23.05.2026 (запланировано)
- Figma-аккаунт для отрисовки SVG-логотипов (если решим не использовать оригиналы)
- Скриншоты реального бота — Катя делает с прод-аккаунта

---

## 14. Финальный чеклист 10/10

Проверка перед мержем в main:

### 5-секундный тест
- [ ] Откройте сайт в инкогнито, дайте посмотреть человеку, который не знает про EDL OS
- [ ] За 5 секунд он должен ответить: «Что они продают?» одним предложением
- [ ] Если ответ содержит слова «маржа», «отчёт», «бизнес-чекап» — пройден
- [ ] Если ответ «не понял» — H1 надо ещё доработать

### Hero
- [ ] H1 говорит о боли или результате, не о метафоре
- [ ] Hero-визуал не пустой (GIF играет / постер виден)
- [ ] Один primary CTA, не два
- [ ] Trust-strip с реальными лого (не эмодзи)

### Скролл по странице
- [ ] Минимум 4 изображения / скриншота на главной (PDF, TG-сводка, ИИ-консультант, НДС-карта)
- [ ] Минимум 1 кейс с реальными цифрами (даже анонимный)
- [ ] Pricing-блок ПОСЛЕ proof-of-value, не сразу

### Технически
- [ ] Lighthouse Performance ≥ 85 (GIF/видео не должны топить)
- [ ] Mobile-first: всё работает на 375×667
- [ ] Reduced motion: видео заменяется на статичный poster
- [ ] Alt-тексты на всех картинках
- [ ] Lighthouse Accessibility ≥ 95

### Конверсия
- [ ] У всех CTA есть `data-cta-type` и `data-cta-location` (для аналитики)
- [ ] Аналитика отслеживает: hero CTA клик, pain section CTA клик, case CTA клик
- [ ] A/B-flag готов: можно за 5 минут вернуть старый H1 если новый не сработает

---

## 15. Файлы — карта изменений

```
# Главное (P1)
~ index.html                                                — Hero + Pain + What you get + ICP move
+ assets/hero-demo.mp4 / .webm / -poster.jpg               — Hero видео-демо (внешняя задача)
+ assets/screenshots/audit-pdf-preview.png                 — Превью PDF
+ assets/screenshots/tg-morning-summary.png                — Превью TG
+ assets/screenshots/tg-ai-consultant.png                  — Превью ИИ-чата
+ assets/screenshots/vat-map-2026.png                      — Превью НДС-карты
+ assets/logos/{1c,amocrm,bitrix,tinkoff,getcourse}.svg    — Trust-strip
~ css/main-v2.css                                           — .hero__bullets, .pain-card, .hero-demo-frame, prefers-reduced-motion

# Audit / Methodology (P2)
~ audit.html                                                — Hero video (после 23.05), визуал bundle-grid
~ methodology.html                                          — Slepye pyatna SVG диаграммы, success-state email-gate

# Прочее (P3)
~ pricing.html                                              — Иконки продуктов
~ cases.html                                                — Убрать placeholders, добавить 1 анонимный кейс
~ about.html                                                — Фото Кати, команда
~ js/main.js                                                — Удалить tg-trigger / icp-switcher из hero, оставить в ICP-section

# Бэкенд (параллельно)
+ edl-os-bot/src/leads/                                     — Cherry-pick из claude/website-v4-updates
+ edl-os-bot/alembic/versions/0012_whitepaper_leads.py     — Перенумерованная миграция
~ edl-os-bot/src/db/models.py                              — Добавить WhitepaperLead после WidgetSession
~ edl-os-bot/src/main.py                                   — include leads_router
```

---

## 16. Зафиксированные решения (согласовано 2026-05-18)

Все 6 открытых вопросов закрыты пользователем «согласовываю». Финальный набор решений:

| # | Решение | Обоснование |
|---|---|---|
| **1** | **MP4 + WebM + статичный poster.** Не GIF. | Лучшая поддержка, легче, autoplay везде, есть `prefers-reduced-motion` fallback |
| **2** | **Сценарий из §4.3 финальный.** Запись screen-cast: Катя (4ч записи в реальном TG-боте) + монтаж в DaVinci Resolve (2ч) = 6ч общего времени. До съёмки в hero показывается статичный poster. | Время блокирует hero; статичный poster закрывает 80% эффекта на старте |
| **3** | **Анонимный кейс «B2B-услуги · 35 человек» с 19.05.** После раскрытия NDA 22.05 — заменим на реальное имя Vitaconsult с фото CFO (с разрешения). | Не блокируем главную лишний день |
| **4** | **Ветка `claude/website-v4-updates` — закрыть PR без мержа.** Cherry-pick только `src/leads/` + миграция 0012 + docs в новую ветку `claude/leads-endpoint` (§11). | Большая часть работы продублирована параллельной сессией; не теряем уникальное — leads-endpoint и доки |
| **5** | **Лого интеграций — оригиналы с grayscale-фильтром + opacity 0.75.** | Юридически безопасный soft-usage; визуально лучше wordmark |
| **6** | **План реализации 19–24.05 — принят** (см. таблицу ниже) | — |

### 16.1 План реализации 19–24.05.2026 (согласован)

| Дата | Утро | Вечер |
|---|---|---|
| **19.05 пн** | Hero (§4) — статичный poster + новый H1 + bullets + 1 primary CTA. Pain section (§5). | Leads-endpoint cherry-pick (§11). Закрыть PR `claude/website-v4-updates`. |
| **20.05 вт** | What you get (§6) с 4 скриншотами. ICP-демо вниз (§7). | Запись скриншотов из реального бота (Катя). Начало записи GIF/MP4 сценария. |
| **21.05 ср** | Кейс-плейсхолдер (§8) «B2B-услуги · 35 чел». audit.html визуал (§9). | Methodology SVG-диаграммы (§10). |
| **22.05 чт** | NDA раскрытие → обновление кейса на реальный (Vitaconsult). Try-in-claude (§12.5) — заменить «скоро» на «доступно». | Остальные страницы (pricing, faq, cases, about — чеклистом, §12). |
| **23.05 пт** | Съёмка видео Кати для audit.html hero. | Финал audit.html с готовым видео. |
| **24.05 сб** | Финал hero — заменить статичный poster на MP4-демо. 5-секундный тест на 3 живых людях. | Релиз: merge в main, наблюдаем метрики. |

---

## 17. Ссылки на источники

- **Репо**: <https://github.com/evzhiganova8888-hub/edl-site>
- **Прод сайт**: <https://elephantdreams.ru>
- **Прод бот**: <https://t.me/edl_os_bot>
- **API**: <https://api.elephantdreams.ru>
- **Railway**: проект `efficient-appreciation`, сервис `edl-site`
- **DNS**: REG.RU, домен `elephantdreams.ru`
- **Бот source-of-truth**: `edl-os-bot/CLAUDE.md`
- **Параллельная сессия 18.05**: `~/Downloads/EDL_Session_Summary_20260518.md`
- **Прошлые работы этой сессии**:
  - `docs/website_v4_status_2026-05-18.md`
  - `docs/backend_widget_deploy_2026-05-18.md`
  - `docs/dns_setup_api_subdomain_2026-05-18.md`

---

## 18. Глоссарий

| Термин | Что значит |
|---|---|
| **EDL OS** | Бренд продукта. **E**lephant **D**reams **L**ab **O**perating **S**ystem. |
| **Founder OS Score** | Mini-Чекап. 12 вопросов, бесплатно, Score 0–100. Lead-magnet. |
| **Бизнес-чекап** | Базовый платный продукт. 9 000 ₽ Base / 14 000 ₽ Plus. 20 вопросов в боте, PDF за 24ч. |
| **НДС-карта 2026** | Часть PDF-чекапа: какие из контрактов клиента под риском из-за ФЗ 425. |
| **MCP** | Model Context Protocol (Anthropic). Open source сервер, который даёт Score внутри Claude Desktop. |
| **CRAFT** | Методология осознанного выбора (Центр CRAFT, школа инноваций ИКРА). |
| **AI Fluency** | Рамка от Anthropic + UCC + Ringling — когда отдавать ИИ, когда оставить человеку. |
| **5-секундный тест** | UX-методика: показать страницу на 5 сек, спросить «что они делают». Источник: NN/g. |
| **ICP** | Ideal Customer Profile — целевой сегмент бизнеса. |
| **NDA до 22.05** | Соглашение с клиентом Vitaconsult — раскрытие имени только после 22.05.2026. |

---

## 19. Visual specs (wireframes + SVG + source-of-truth)

> **Назначение раздела.** Прошлые секции описали ЧТО менять. Этот раздел описывает КАК это должно выглядеть пиксель в пиксель — в стиле Figma source-of-truth.
> Все размеры, цвета, отступы — из реальных `css/tokens.css` и `css/main-v2.css`. Если в плане встречается «sm padding» — это всегда `var(--space-2)` (8px), а не «как-то 8 примерно».

### 19.1 Дизайн-токены (canonical, не переизобретать)

**Источник:** `css/tokens.css`. Используем готовые CSS-переменные.

```text
БРЭНД
  --color-tangerine:        #FF6B1A    (Electric Tangerine — primary brand)
  --color-tangerine-hover:  #E55A0A
  --color-tangerine-light:  #FFE5D9    (бэкграунды бейджей)

НЕЙТРАЛЬНЫЕ
  --color-black:    #0A0A0A    (header logo, h1 текст)
  --color-dark:     #1A1A1A    (dark sections)
  --color-gray-900: #171717    (заголовки h2-h4)
  --color-gray-700: #404040    (body text, subtitle)
  --color-gray-500: #737373    (caption text)
  --color-gray-300: #D4D4D4    (borders)
  --color-gray-200: #E5E5E5    (dividers, card borders)
  --color-gray-100: #F5F5F5    (section--gray bg)
  --color-off-white:#FAFAFA    (default page bg)

СЕМАНТИКА
  --color-success: #10B981   (зелёный для PDF отправлен)
  --color-warning: #F59E0B
  --color-error:   #EF4444

ТИПОГРАФИКА
  --font-sans:  'Inter', sans-serif
  --font-mono:  'JetBrains Mono', monospace

  --font-size-h1:      clamp(2.5rem, 5vw+1rem, 5rem)
  --font-size-h2:      clamp(2rem,   3.5vw+0.5rem, 3.5rem)
  --font-size-h3:      clamp(1.5rem, 2vw+0.5rem, 2rem)
  --font-size-body:    clamp(1rem,   0.5vw+0.875rem, 1.125rem)
  --font-size-caption: 0.8125rem

SPACING (8pt grid)
  --space-1:  4px    --space-2: 8px     --space-3: 12px   --space-4: 16px
  --space-6:  24px   --space-8: 32px    --space-12: 48px  --space-16: 64px
  --space-24: 96px   --space-32: 128px

RADII
  --radius-sm: 4px    --radius-md: 8px     --radius-lg: 16px
  --radius-xl: 24px   --radius-tg: 18px    --radius-full: 9999px

SHADOWS
  --shadow-sm:          0 1px 2px  rgba(0,0,0,0.05)
  --shadow-md:          0 4px 12px rgba(0,0,0,0.08)
  --shadow-lg:          0 8px 24px rgba(0,0,0,0.12)
  --shadow-card-hover:  0 8px 30px rgba(255,107,26,0.15)

LAYOUT
  --max-width:      1280px
  --content-width:  1216px
  --grid-gap-desktop: 32px
  --grid-gap-tablet:  24px
  --grid-gap-mobile:  16px

BREAKPOINTS (PR #37 canonical)
  xs:  ≤ 480px
  sm:  481–767px
  md:  768–1023px      ← header switches from burger to nav
  lg:  ≥ 1024px        ← hero grid becomes 2-col
  xl:  ≥ 1280px

MOTION
  --ease-default: cubic-bezier(0.16, 1, 0.3, 1)
  --ease-bounce:  cubic-bezier(0.34, 1.56, 0.64, 1)
```

**Существующие готовые классы** (НЕ переизобретать, использовать как есть):

| Класс | Где определён | Назначение |
|---|---|---|
| `.btn`, `.btn--primary`, `.btn--outline` | `css/components.css` | Кнопки (primary = tangerine, outline = бордер) |
| `.section`, `.section--gray` | `css/main.css` / `main-v2.css` | Padding 80px 0, gray bg для секций-разделителей |
| `.container` | `css/main.css` | max-width 1216px, mx-auto, padding 24px |
| `.hero__bullets`, `.hero__bullets li` | `css/main-v2.css:160-180` | Уже есть! НЕ писать inline-стили |
| `.section__title` | `css/main-v2.css` | H2 align-center, font-size-h2, margin-bottom |
| `.trust-strip`, `.trust-strip__badge`, `.trust-strip__sep` | `css/main-v2.css` | Текущий strip с эмодзи — будем менять стилем, классы оставим |
| `.bundle-grid` | `css/main-v2.css:529` | 4-col grid с responsive 2-col на md и 1-col на xs |
| `.video-placeholder`, `.video-placeholder__icon` | `css/main-v2.css:512` | Для статичного poster пока нет видео |
| `.case-card`, `.case-stats` | НЕТ — создать в `main-v2.css` | См. §19.7 |
| `.pain-card`, `.pain-grid` | НЕТ — создать в `main-v2.css` | См. §19.4 |
| `.hero-demo-frame`, `.hero-demo-video`, `.hero-demo-caption` | НЕТ — создать в `main-v2.css` | См. §19.2 |

**Правило**: новый код пишем CSS-классы (НЕ inline-styles), кладём в `css/main-v2.css` в конец файла с блоком-разделителем:
```css
/* ── UX v5 (2026-05-18) — hero refresh + pain section + visual case ── */
```

---

### 19.2 Hero — wireframe (desktop, ≥ 1024px)

Контейнер: `.container` (max-width 1216px), `.hero__grid` (2 колонки 1:1 с gap 64px).

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  HEADER (sticky)                                                              │  ← 72px
│  [EDL OS] [Методология] [Claude/MCP] [Кейсы] [Цены] [Команда] [FAQ] [Канал✈] │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌──────────────────────────────┐  ┌────────────────────────────────────┐   │
│  │ ◀── 576px ────────────────▶ │  │ ◀────── 576px ──────────────────▶ │   │
│  │                              │  │                                    │   │
│  │ Видеть, где утекает          │  │  ┌──────────────────────────┐    │   │
│  │ маржа вашего бизнеса —       │  │  │                          │    │   │
│  │ ежедневно, а не              │  │  │   ╔══════════════════╗   │    │   │
│  │ раз в квартал. ◂─ tangerine  │  │  │   ║ EDL OS Bot       ║   │    │   │
│  │  (clamp 2rem..3.5rem)        │  │  │   ║ онлайн           ║   │    │   │
│  │                              │  │  │   ╠══════════════════╣   │    │   │
│  │ ▸ Каждый клиент в плюсе      │  │  │   ║ 📊 Маржа -2.1пп  ║   │    │   │
│  │   или в минусе — видно сразу │  │  │   ║                  ║   │    │   │
│  │ ▸ НДС 2026 посчитан…         │  │  │   ║ 🔥 HOT: Петров   ║   │    │   │
│  │ ▸ Сводка в Telegram          │  │  │   ║    1.2M, 28ч…    ║   │    │   │
│  │                              │  │  │   ║                  ║   │    │   │
│  │ ┌────────────────┐  Или      │  │  │   ║ 💰 НДС 2026:     ║   │    │   │
│  │ │  Получить      │ Score     │  │  │   ║    +180k к плану ║   │    │   │
│  │ │  чекап 9000 ₽ →│ бесплатно │  │  │   ║                  ║   │    │   │
│  │ └────────────────┘ (link)    │  │  │   ║  ▼ Открыть PDF   ║   │    │   │
│  │   primary tangerine          │  │  │   ╚══════════════════╝   │    │   │
│  │                              │  │  │                          │    │   │
│  │ Интеграции:                  │  │  │   AUTOPLAY MP4 (loop)    │    │   │
│  │ [1С][amoCRM][Б24][Тинь][ГК]  │  │  └──────────────────────────┘    │   │
│  │ ← grayscale, opacity 0.75    │  │      380×570px (aspect 2:3)       │   │
│  │                              │  │                                    │   │
│  │ 152-ФЗ · возврат 14 дней     │  │  «Так выглядит работа собственника│   │
│  │ Open source MCP              │  │   через 14 дней после Чекапа»     │   │
│  │ ← caption color-gray-500     │  │      ← font-size-caption          │   │
│  └──────────────────────────────┘  └────────────────────────────────────┘   │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
   ↑ padding-top 120px (учитывает sticky header)
   padding-bottom 96px
```

**CSS для новой структуры** (добавить в `css/main-v2.css` в конец):

```css
/* ── UX v5 (2026-05-18) — Hero refresh ── */

.hero__grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-12);
  align-items: center;
}
@media (min-width: 1024px) {
  .hero__grid {
    grid-template-columns: 1fr 1fr;
    gap: var(--space-16);
  }
}

.hero__title {
  font-size: var(--font-size-h1);
  line-height: 1.05;
  letter-spacing: -0.02em;
  color: var(--color-gray-900);
  margin-bottom: var(--space-6);
  font-weight: 700;
}
.hero__title-accent {
  color: var(--color-tangerine);
  white-space: normal;
}

.hero-demo-frame {
  position: relative;
  max-width: 380px;
  margin: 0 auto;
  aspect-ratio: 2 / 3;
}
.hero-demo-video {
  width: 100%;
  height: 100%;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  display: block;
  object-fit: cover;
  background: var(--color-gray-100);
}
.hero-demo-caption {
  text-align: center;
  margin-top: var(--space-3);
  font-size: var(--font-size-caption);
  color: var(--color-gray-500);
  line-height: 1.4;
}

@media (prefers-reduced-motion: reduce) {
  .hero-demo-video { display: none; }
  .hero-demo-frame::before {
    content: '';
    display: block;
    width: 100%;
    height: 100%;
    background: url('/assets/hero-demo-poster.jpg') center/cover no-repeat;
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-lg);
  }
}

.hero__secondary-cta {
  background: none;
  border: none;
  color: var(--color-tangerine);
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
  font: inherit;
  font-size: var(--font-size-small);
  padding: 0;
}
.hero__secondary-cta:hover { color: var(--color-tangerine-hover); }

.trust-logos {
  display: flex;
  gap: var(--space-6);
  align-items: center;
  flex-wrap: wrap;
  margin-top: var(--space-6);
  opacity: 0.75;
}
.trust-logos__label {
  font-size: var(--font-size-caption);
  color: var(--color-gray-500);
  font-weight: 500;
}
.trust-logos img {
  height: 24px;
  width: auto;
  filter: grayscale(1);
  transition: opacity .2s var(--ease-default);
}
.trust-logos img:hover { filter: grayscale(0); opacity: 1; }

.trust-line {
  margin-top: var(--space-3);
  font-size: var(--font-size-caption);
  color: var(--color-gray-500);
  line-height: 1.5;
}
```

---

### 19.3 Hero — wireframe (mobile, ≤ 480px)

Колонка одна. Видео переезжает над текстом — пользователь сразу видит продукт, потом читает.

```
┌─────────────────────────────────┐  ← 360px viewport
│ [☰] EDL OS         [✈ Канал]   │  ← header
├─────────────────────────────────┤
│   ┌─────────────────────────┐   │
│   │                          │   │
│   │   ╔══════════════════╗   │   │
│   │   ║ EDL OS Bot       ║   │   │
│   │   ║ онлайн           ║   │   │
│   │   ╠══════════════════╣   │   │
│   │   ║ 📊 Маржа ↓2.1пп  ║   │   │
│   │   ║                  ║   │   │
│   │   ║ 🔥 HOT: Петров   ║   │   │
│   │   ╚══════════════════╝   │   │
│   │      MP4 320×480px       │   │
│   └─────────────────────────┘   │
│   «Так работает собственник…»   │
│                                  │
│ Видеть, где утекает              │
│ маржа — ежедневно,               │
│ а не раз в квартал.              │
│   (font-size clamp 2rem)         │
│                                  │
│ ▸ Каждый клиент в плюсе          │
│   или в минусе — видно сразу     │
│ ▸ НДС 2026 в PDF за 24ч          │
│ ▸ Сводка в Telegram каждое утро  │
│                                  │
│ ┌─────────────────────────────┐ │
│ │ Получить чекап за 9 000 ₽ → │ │  ← full width
│ └─────────────────────────────┘ │
│ Или попробуйте Score бесплатно   │
│                                  │
│ Интеграции:                      │
│ [1С] [amoCRM]                   │
│ [Б24] [Тиньк] [ГК]              │
│                                  │
│ 152-ФЗ · возврат 14 дней         │
└─────────────────────────────────┘
```

**Mobile CSS** (доп. правила):

```css
@media (max-width: 1023px) {
  .hero__grid > .hero__demo { order: -1; }   /* видео сверху на мобайле */
  .hero-demo-frame { max-width: 320px; }
}

@media (max-width: 480px) {
  .hero { padding-top: var(--space-24); padding-bottom: var(--space-12); }
  .btn--primary { width: 100%; min-height: 56px; }
  .hero__secondary-cta { display: block; margin-top: var(--space-3); }
}
```

---

### 19.4 Hero video — storyboard (12 секунд, 6 кадров)

Раскадровка для записи. Каждый кадр = 2 секунды. Aspect ratio 2:3 (380×570px desktop, 320×480px mobile).

```
┌── Кадр 1 (0:00–0:02) ─────────────┐   ┌── Кадр 2 (0:02–0:04) ─────────────┐
│  ╔══════════════════╗             │   │  ╔══════════════════╗             │
│  ║ ◀ EDL OS Bot     ║             │   │  ║ ◀ EDL OS Bot     ║             │
│  ║   онлайн         ║             │   │  ║   онлайн         ║             │
│  ╠══════════════════╣             │   │  ╠══════════════════╣             │
│  ║                  ║             │   │  ║ 📊 Сводка        ║             │
│  ║   (пусто)        ║             │   │  ║   19 мая:        ║             │
│  ║                  ║             │   │  ║                  ║             │
│  ║                  ║             │   │  ║ Маржа -2.1 п.п.  ║             │
│  ║                  ║             │   │  ║ к плану. 3/24    ║             │
│  ║                  ║             │   │  ║ клиента в минус. ║             │
│  ╚══════════════════╝             │   │  ╚══════════════════╝             │
│  Заглавный экран                   │   │  Появилось 1-е сообщение           │
│  (статика 2 сек, для poster)      │   │  с анимацией «набирается»          │
└────────────────────────────────────┘   └────────────────────────────────────┘

┌── Кадр 3 (0:04–0:06) ─────────────┐   ┌── Кадр 4 (0:06–0:08) ─────────────┐
│  ╠══════════════════╣             │   │  ╠══════════════════╣             │
│  ║ 📊 Маржа -2.1пп  ║             │   │  ║ 📊 Маржа -2.1пп  ║             │
│  ║                  ║             │   │  ║ 🔥 HOT-сделки:   ║             │
│  ║ 🔥 HOT-сделки:   ║             │   │  ║   Петров 1.2М    ║             │
│  ║   Петров 1.2М    ║             │   │  ║   без касания 28ч║             │
│  ║   без касания 28ч║             │   │  ║                  ║             │
│  ║                  ║             │   │  ║ 💰 НДС 2026:     ║             │
│  ║                  ║             │   │  ║   +180 000 ₽     ║             │
│  ║                  ║             │   │  ║   к плану        ║             │
│  ║                  ║             │   │  ║                  ║             │
│  ╚══════════════════╝             │   │  ║ ┌──────────────┐ ║             │
│  Появилось 2-е сообщение           │   │  ║ │📄 Открыть PDF│ ║             │
│                                    │   │  ║ └──────────────┘ ║             │
│                                    │   │  ╚══════════════════╝             │
│                                    │   │  3-е сообщение + inline-кнопка     │
└────────────────────────────────────┘   └────────────────────────────────────┘

┌── Кадр 5 (0:08–0:10) ─────────────┐   ┌── Кадр 6 (0:10–0:12) ─────────────┐
│  ╔══════════════════╗             │   │  ╔══════════════════╗             │
│  ║ Бизнес-чекап     ║             │   │  ║ Бизнес-чекап     ║             │
│  ║ ─────────────    ║             │   │  ║ ─────────────    ║             │
│  ║ 4 слоя:          ║             │   │  ║                  ║             │
│  ║                  ║             │   │  ║   EDL OS         ║             │
│  ║ • Стратегия      ║             │   │  ║   ────────       ║             │
│  ║ • Воронка        ║             │   │  ║                  ║             │
│  ║ • Операционка    ║             │   │  ║ 24 часа на       ║             │
│  ║ • Деньги         ║             │   │  ║ полную картину   ║             │
│  ║                  ║             │   │  ║                  ║             │
│  ║ [НДС-карта 2026] ║             │   │  ║                  ║             │
│  ║ ┃▓▓▓▓▓░░░░░░░░░ ║             │   │  ║                  ║             │
│  ║ ┃▓▓▓▓░░░░░░░░░░ ║             │   │  ║                  ║             │
│  ║ ┃▓▓░░░░░░░░░░░░ ║             │   │  ║                  ║             │
│  ╚══════════════════╝             │   │  ╚══════════════════╝             │
│  Переход на PDF: страница НДС      │   │  Затухание + слоган                │
└────────────────────────────────────┘   └────────────────────────────────────┘

ТРАНЗИЦИИ:
- кадр 1 → 2: fade in сообщение
- кадр 2 → 3: scroll up
- кадр 3 → 4: scroll up, появление кнопки
- кадр 4 → 5: cross-fade (TG → PDF)
- кадр 5 → 6: brightness up + EDL OS логотип появляется в центре

ПОСЛЕ КАДРА 6 — loop возвращается к кадру 1 (continuous).
ПЕРВЫЙ КАДР (0:00) — это и есть poster для preload.
```

**Технические требования:**
| Параметр | Значение |
|---|---|
| MP4 codec | h264, baseline profile, 30fps, CRF 28 |
| WebM codec | vp9, CRF 32 |
| Аудио | вырезать (silent) |
| Файл MP4 | ≤ 700 КБ |
| Файл WebM | ≤ 500 КБ |
| Poster | JPG, quality 85, 380×570px, ≤ 80 КБ |

**Где взять контент для съёмки/монтажа:**
1. **Текст сообщений бота** — из реальных system prompts в `edl-os-bot/src/prompts/handoff/services_it.md` или сгенерировать в проде через `@edl_os_bot /start` с фейковой нишей «услуги»
2. **PDF-страница НДС** — открыть `assets/pdf/founder-os-whitepaper/whitepaper.html` стр. 5, скриншот области с таблицей
3. **EDL OS логотип финального кадра** — `assets/logo-192.png` (увеличить до 280×280, центр)
4. **Программа для монтажа**: DaVinci Resolve (бесплатный) или CapCut Pro

---

### 19.5 Pain section — visual layout

Секция после hero, разделитель `.section--gray` (bg: `--color-gray-100`).

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              У вас так?                                       │
│                          ← font-size-h2, центр                                │
│                                                                                │
│   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐│
│   │      📊       │  │      🌪️       │  │      ⚖️       │  │      🤖       ││
│   │  ← 2rem icon  │  │               │  │               │  │               ││
│   │               │  │               │  │               │  │               ││
│   │ Бухгалтерия   │  │ Стратегия     │  │ НДС 2026:     │  │ ИИ хочется,   ││
│   │ раз в месяц,  │  │ живёт в голове│  │ знаете формулу│  │ но непонятно  ││
│   │ факты раз в   │  │ основателя    │  │ но не         │  │ куда          ││
│   │ квартал       │  │               │  │ последствия   │  │               ││
│   │ ← font 1.125rem│  │               │  │               │  │               ││
│   │  font-weight: │  │               │  │               │  │               ││
│   │    600        │  │               │  │               │  │               ││
│   │               │  │               │  │               │  │               ││
│   │ К моменту,    │  │ Команда       │  │ Не понятно,   │  │ Где он реально││
│   │ когда видно   │  │ выросла, но   │  │ какие из ваших│  │ даст пользу,  ││
│   │ убыточный…    │  │ непонятно —   │  │ контрактов…   │  │ а где будет   ││
│   │  ← font 0.9375│  │ куда          │  │               │  │ имитировать   ││
│   │   gray-700    │  │               │  │               │  │               ││
│   └───────────────┘  └───────────────┘  └───────────────┘  └───────────────┘│
│      280px            280px              280px              280px            │
│                                                                                │
│              EDL OS закрывает все четыре пункта за один Бизнес-чекап.        │
│                                                                                │
│                  ┌─────────────────────────────────────┐                      │
│                  │   Заказать чекап за 9 000 ₽ →      │                      │
│                  └─────────────────────────────────────┘                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Адаптив:**
- ≥ 1024px: 4-col grid, gap 24px
- 768–1023px: 2-col grid (по 2 карточки в ряд), gap 24px
- ≤ 767px: 1-col stack, gap 16px

**CSS:**

```css
/* ── UX v5 — Pain section ── */
.pain-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-6);
  margin-bottom: var(--space-12);
}
@media (max-width: 1023px) { .pain-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 767px)  { .pain-grid { grid-template-columns: 1fr; gap: var(--space-4); } }

.pain-card {
  background: var(--color-white);
  padding: var(--space-8) var(--space-6);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-gray-200);
  transition: box-shadow .2s var(--ease-default), transform .2s var(--ease-default);
}
.pain-card:hover {
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-2px);
}
.pain-card__icon {
  font-size: 2rem;
  margin-bottom: var(--space-3);
  display: block;
  line-height: 1;
}
.pain-card__title {
  font-weight: 600;
  margin-bottom: var(--space-2);
  font-size: 1.125rem;
  color: var(--color-gray-900);
  line-height: 1.3;
}
.pain-card__text {
  color: var(--color-gray-700);
  font-size: 0.9375rem;
  line-height: 1.5;
  margin: 0;
}
```

---

### 19.6 What you get — карточки со скриншотами

После Pain section. Сетка 4 карточки → 2×2 на md → 1-col на xs. Каждая — с скриншотом 400×300 сверху и текстом снизу.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                Что вы получите от Бизнес-чекапа за 24 часа                    │
│                                                                                │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐       │
│  │  ┌────────────────────────┐  │    │  ┌────────────────────────┐  │       │
│  │  │  [скрин PDF — стр.1]   │  │    │  │  [скрин TG — сводка]   │  │       │
│  │  │   400×240px            │  │    │  │   400×240px            │  │       │
│  │  │   радиус 16px          │  │    │  │                        │  │       │
│  │  │   shadow-md            │  │    │  │                        │  │       │
│  │  └────────────────────────┘  │    │  └────────────────────────┘  │       │
│  │                                │    │                                │       │
│  │  PDF-чекап за 24 часа         │    │  Утренняя сводка в Telegram   │       │
│  │  ← font 1.25rem weight 700    │    │                                │       │
│  │  ← color gray-900             │    │                                │       │
│  │                                │    │                                │       │
│  │  10-15 страниц с НДС-картой   │    │  Каждое утро — что произошло  │       │
│  │  2026 и 5-7 конкретными       │    │  с маржой, какие сделки горят,│       │
│  │  рекомендациями.              │    │  где утечка денег.            │       │
│  │  ← font 0.9375 gray-700       │    │                                │       │
│  └──────────────────────────────┘    └──────────────────────────────┘       │
│                                                                                │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐       │
│  │  ┌────────────────────────┐  │    │  ┌────────────────────────┐  │       │
│  │  │  [скрин ИИ-чата]       │  │    │  │  [скрин НДС-карты]     │  │       │
│  │  │   400×240px            │  │    │  │   400×240px            │  │       │
│  │  └────────────────────────┘  │    │  └────────────────────────┘  │       │
│  │                                │    │                                │       │
│  │  ИИ-консультант под рукой     │    │  НДС-карта 2026               │       │
│  │                                │    │                                │       │
│  │  Спросите бота про любой      │    │  Какие из ваших контрактов    │       │
│  │  слой бизнеса — он ответит    │    │  под риском из-за ФЗ 425.     │       │
│  │  на базе ваших данных.        │    │  Готовая дорожная карта.      │       │
│  └──────────────────────────────┘    └──────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────────────┘
```

**CSS:** использовать существующий `.bundle-grid` (есть в `main-v2.css:529`). Расширяем:

```css
/* ── UX v5 — What you get cards with screenshots ── */
.value-card {
  background: var(--color-white);
  border: 1px solid var(--color-gray-200);
  border-radius: var(--radius-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: box-shadow .2s var(--ease-default);
}
.value-card:hover { box-shadow: var(--shadow-card-hover); }
.value-card__screenshot {
  display: block;
  width: 100%;
  aspect-ratio: 5 / 3;
  object-fit: cover;
  background: var(--color-gray-100);
}
.value-card__body { padding: var(--space-6); }
.value-card__title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-gray-900);
  margin: 0 0 var(--space-2);
}
.value-card__text {
  font-size: 0.9375rem;
  color: var(--color-gray-700);
  line-height: 1.55;
  margin: 0;
}
```

---

### 19.7 Case-card — visual layout

Внутри секции «Уже работает». Один большой блок (не grid), max-width 720px.

```
┌────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   ┌──┐                                                                   │
│   │🏢│  B2B-услуги · 35 сотрудников                                     │
│   └──┘  Внедрение EDL OS · 4 недели                                     │
│   ← 64px circle, bg tangerine-light                                     │
│                                                                          │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  «Узнали, что 3 из 24 клиентов работают в минус.                       │
│   Перезаключили — маржа +4 п.п. за квартал.»                            │
│  ← font 1.375rem weight 600 — quote                                     │
│                                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                        │
│  │            │  │            │  │            │                        │
│  │   3 из 24  │  │   +4 п.п.  │  │   28 дней  │                        │
│  │  ← 2rem    │  │            │  │            │                        │
│  │  tangerine │  │            │  │            │                        │
│  │  weight 700│  │            │  │            │                        │
│  │            │  │            │  │            │                        │
│  │ убыточных  │  │   маржа    │  │  до первых │                        │
│  │ контрактов │  │ за квартал │  │ результатов│                        │
│  │  нашли     │  │            │  │            │                        │
│  │ ← 0.875    │  │            │  │            │                        │
│  │ gray-600   │  │            │  │            │                        │
│  └────────────┘  └────────────┘  └────────────┘                        │
│  bg gray-50, radius 12, padding 16                                      │
│                                                                          │
│  До: ручные отчёты в Excel раз в квартал, маржа считалась               │
│  по компании в целом. После: каждое утро сводка в Telegram              │
│  с проблемными клиентами + PDF-разбор по 4 слоям. Команда не выросла.   │
│  ИТ-внедрений не было.                                                  │
│  ← font 1rem gray-700 line-height 1.6                                   │
│                                                                          │
│  ───────────────────────────────────────────────────────────────────    │
│  NDA — название компании раскроем после 22.05.2026.                     │
│  Цифры подтверждены реальной отчётностью.                               │
│  ← font 0.875 gray-600 italic                                           │
└────────────────────────────────────────────────────────────────────────┘
   ← padding 32px, border 1 gray-200, radius 20
```

**CSS:**

```css
/* ── UX v5 — Case card ── */
.case-card {
  background: var(--color-white);
  padding: var(--space-8);
  border-radius: 20px;
  border: 1px solid var(--color-gray-200);
  max-width: 720px;
  margin: 0 auto;
}
.case-card__header { display: flex; gap: var(--space-4); align-items: center; margin-bottom: var(--space-6); }
.case-card__avatar {
  width: 64px; height: 64px;
  background: var(--color-tangerine-light);
  border-radius: var(--radius-full);
  display: flex; align-items: center; justify-content: center;
  font-size: 1.75rem;
}
.case-card__company { font-weight: 700; font-size: 1.125rem; color: var(--color-gray-900); }
.case-card__meta { font-size: 0.875rem; color: var(--color-gray-500); }

.case-card__quote {
  font-size: 1.375rem;
  font-weight: 600;
  line-height: 1.35;
  color: var(--color-gray-900);
  margin: var(--space-6) 0;
}

.case-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  margin: var(--space-6) 0;
}
@media (max-width: 480px) { .case-stats { grid-template-columns: 1fr; } }

.case-stat {
  text-align: center;
  padding: var(--space-4);
  background: var(--color-gray-50);
  border-radius: var(--radius-md);
}
.case-stat__number {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-tangerine);
  line-height: 1;
}
.case-stat__label {
  font-size: 0.875rem;
  color: var(--color-gray-600);
  margin-top: var(--space-2);
  line-height: 1.3;
}

.case-card__story {
  color: var(--color-gray-700);
  line-height: 1.6;
  font-size: 1rem;
  margin: var(--space-4) 0 0;
}
.case-card__footer {
  margin-top: var(--space-6);
  padding-top: var(--space-6);
  border-top: 1px solid var(--color-gray-200);
  font-size: 0.875rem;
  color: var(--color-gray-500);
  font-style: italic;
}
```

---

### 19.8 Methodology SVG-диаграммы (inline, не картинки)

Для 3-х блоков «слепых пятен» в `methodology.html`. Все SVG inline в HTML, цвета из токенов, дублируются в light/dark.

**SVG #1 — «Не вижу куда уплывает маржа»** (4 столбика, 1 красный)

```html
<svg width="280" height="160" viewBox="0 0 280 160" xmlns="http://www.w3.org/2000/svg"
     role="img" aria-label="Маржа по клиентам: 3 в плюсе, 1 в минусе">
  <!-- Базовая линия -->
  <line x1="20" y1="130" x2="260" y2="130" stroke="#E5E5E5" stroke-width="2"/>
  <!-- 4 столбца -->
  <rect x="40"  y="60"  width="40" height="70" rx="4" fill="#FF6B1A" opacity="0.85"/>
  <rect x="100" y="40"  width="40" height="90" rx="4" fill="#FF6B1A" opacity="0.85"/>
  <rect x="160" y="50"  width="40" height="80" rx="4" fill="#FF6B1A" opacity="0.85"/>
  <rect x="220" y="100" width="40" height="30" rx="4" fill="#EF4444"/>
  <!-- Метки -->
  <text x="60"  y="148" text-anchor="middle" font-family="Inter" font-size="11" fill="#737373">Клиент A</text>
  <text x="120" y="148" text-anchor="middle" font-family="Inter" font-size="11" fill="#737373">Клиент B</text>
  <text x="180" y="148" text-anchor="middle" font-family="Inter" font-size="11" fill="#737373">Клиент C</text>
  <text x="240" y="148" text-anchor="middle" font-family="Inter" font-size="11" fill="#EF4444" font-weight="600">в минусе</text>
</svg>
```

**SVG #2 — «Нет времени думать стратегически»** (стопка задач горит)

```html
<svg width="200" height="160" viewBox="0 0 200 160" xmlns="http://www.w3.org/2000/svg"
     role="img" aria-label="Стопка задач с огоньком сверху">
  <!-- Стопка прямоугольников-задач -->
  <rect x="40" y="100" width="120" height="20" rx="4" fill="#E5E5E5"/>
  <rect x="45" y="80"  width="110" height="20" rx="4" fill="#D4D4D4"/>
  <rect x="50" y="60"  width="100" height="20" rx="4" fill="#A3A3A3"/>
  <rect x="55" y="40"  width="90"  height="20" rx="4" fill="#737373"/>
  <!-- Огонь сверху -->
  <path d="M 95 35 C 85 25, 90 15, 100 5 C 110 15, 115 25, 105 35 Z" fill="#FF6B1A"/>
  <path d="M 98 32 C 92 24, 96 18, 100 12 C 104 18, 108 24, 102 32 Z" fill="#FFE5D9"/>
  <!-- Подпись -->
  <text x="100" y="148" text-anchor="middle" font-family="Inter" font-size="12" fill="#737373">
    Стратегия живёт в голове
  </text>
</svg>
```

**SVG #3 — «Граница с ИИ»** (диаграмма Венна: человек / AI / совместно)

```html
<svg width="280" height="160" viewBox="0 0 280 160" xmlns="http://www.w3.org/2000/svg"
     role="img" aria-label="Зоны ответственности: человек, ИИ и совместная работа">
  <!-- Круг человека -->
  <circle cx="105" cy="80" r="55" fill="#FF6B1A" opacity="0.25"/>
  <!-- Круг ИИ -->
  <circle cx="175" cy="80" r="55" fill="#0A0A0A" opacity="0.15"/>
  <!-- Тексты -->
  <text x="75"  y="85" text-anchor="middle" font-family="Inter" font-size="12" font-weight="600" fill="#171717">Человек</text>
  <text x="205" y="85" text-anchor="middle" font-family="Inter" font-size="12" font-weight="600" fill="#171717">ИИ</text>
  <text x="140" y="85" text-anchor="middle" font-family="Inter" font-size="11" font-weight="600" fill="#FF6B1A">Совместно</text>
  <!-- Подпись -->
  <text x="140" y="148" text-anchor="middle" font-family="Inter" font-size="12" fill="#737373">
    AI Fluency Framework
  </text>
</svg>
```

Все три SVG вставляются в существующие `<article class="meth-block">` в `methodology.html` — после `<h3 class="meth-problem">`, перед `<p>`.

---

### 19.9 Trust-strip logos — fallback wordmark

Если оригиналы лого с brand-guidelines подобрать не успеваем — на стартовый релиз делаем **SVG-wordmark в Inter Bold**. Цвет `#737373` (gray-500), opacity 0.75 на странице.

```html
<svg width="60" height="24" viewBox="0 0 60 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <text x="0" y="18" font-family="Inter, sans-serif" font-size="16" font-weight="700" fill="#737373">1С</text>
</svg>
```

Заменить `1С` на каждый бренд: `amoCRM`, `Битрикс24`, `Тинькофф`, `GetCourse`.

**После 24.05** — заменить wordmark на оригинальные SVG из brand-kits:
- 1С: <https://1c.ru/news/info.jsp?id=24180>
- amoCRM: <https://www.amocrm.ru/brand/>
- Битрикс24: <https://www.bitrix24.ru/about/press/>
- Тинькофф: <https://www.tinkoff.ru/about/media-center/>
- GetCourse: <https://getcourse.ru/brand>

Положить в `/assets/logos/{1c,amocrm,bitrix,tinkoff,getcourse}.svg`. Размер каждого: высота 24px (width auto), viewBox squarish.

---

### 19.10 Скриншоты — implementation guide

Все скриншоты для секции «Что получите» (§6/19.6) — в `assets/screenshots/`. Размер 800×480px (отображается 400×240, retina 2x).

**Файл 1: `audit-pdf-preview.png`**
1. Открой `assets/audit_sample.html` в Chrome (это существующий пример отчёта из бота)
2. Установи viewport 800×1100 (DevTools → Device Toolbar)
3. Скриншот первой страницы (DevTools → Cmd+Shift+P → "Capture full size screenshot")
4. Crop в Figma/Preview до 800×480, оставить заголовок + первый блок «4 слоя»
5. Сохранить PNG, оптимизировать через TinyPNG → ≤ 80 КБ

**Файл 2: `tg-morning-summary.png`**
1. Запустить @edl_os_bot в Telegram Desktop, тёмная тема выключена
2. Отправить себе `/start audit` и пройти первый шаг до сообщения «Маржа по проектам мая…»
3. Скриншот окна Telegram (только область чата), 800×480
4. Замазать в Figma личные данные (имя в шапке → «EDL OS · Demo»)
5. Сохранить PNG, ≤ 80 КБ

**Файл 3: `tg-ai-consultant.png`**
1. Тот же бот, отправить вопрос «А какой клиент сейчас самый убыточный?»
2. Скриншот ответа Claude Haiku 800×480
3. Замазать персональные данные
4. Сохранить PNG, ≤ 80 КБ

**Файл 4: `vat-map-2026.png`**
1. Открыть `assets/pdf/founder-os-whitepaper/whitepaper.html` (single-source whitepaper)
2. Перейти на страницу 5 (там НДС-карта/сравнительная таблица)
3. Скриншот области таблицы 800×480
4. Сохранить PNG, ≤ 80 КБ

**Файл 5: `hero-demo-poster.jpg`** (для hero video, до записи MP4 — статичный fallback)
1. Открой Figma → 380×570 frame
2. Нарисуй TG-чат с одним сообщением (как кадр 2 из storyboard §19.4)
3. Export JPG quality 85, ≤ 80 КБ
4. Положить в `/assets/hero-demo-poster.jpg`

---

### 19.11 Pricing icons — что нарисовать

Для секции pricing на главной + `pricing.html`. 5 иконок по 64×64px, SVG, цвет `--color-tangerine` (#FF6B1A) на белом фоне.

| Продукт | Иконка (метафора) |
|---|---|
| Mini-Чекап / Founder OS Score | 📊 → SVG: круговой gauge на 65% |
| Бизнес-чекап | 📄 → SVG: PDF-документ с галочкой |
| Диагностика | 🔍 → SVG: лупа над документом |
| Спринт | ⚙️ → SVG: шестерёнки, две связанные |
| План Роста | 📈 → SVG: восходящий график |

Каждая — простая, line-style stroke 2px. Опционально — нарисовать в Figma, экспорт SVG.

**Стартовый стиль (пример Mini-Чекап gauge):**

```html
<svg width="48" height="48" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <circle cx="24" cy="24" r="18" fill="none" stroke="#E5E5E5" stroke-width="3"/>
  <path d="M 24 6 A 18 18 0 0 1 39.5 32" fill="none" stroke="#FF6B1A" stroke-width="3" stroke-linecap="round"/>
  <text x="24" y="29" text-anchor="middle" font-family="Inter" font-size="12" font-weight="700" fill="#171717">65</text>
</svg>
```

---

### 19.12 About page hero — фото Кати

В `about.html` hero сейчас текст-only. Добавить блок:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                                │
│   ┌──────────────────┐    Я — Екатерина Жиганова.                            │
│   │                  │                                                         │
│   │   ФОТО КАТИ      │    Развиваю EDL OS для бизнесов 10–50 человек.       │
│   │   400×400px      │                                                         │
│   │   радиус 20      │    До этого: 10 лет в Big Tech operations              │
│   │                  │    (McKinsey, Yandex). MBA INSEAD.                     │
│   │                  │                                                         │
│   │                  │    «Я строила оптимизацию для компаний на 5000         │
│   │                  │    человек. Сейчас вижу — те же принципы спасают       │
│   │                  │    бизнес на 30 человек, если переписать их под        │
│   │                  │    Telegram + AI. EDL OS — про это.»                   │
│   │                  │                                                         │
│   │                  │    [LinkedIn]  [Telegram-канал ✈]                      │
│   └──────────────────┘                                                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Спецификация фото:**
- Размер 1000×1000px, оригинал (для retina и Open Graph)
- Светлый или нейтральный фон (не slick studio shot — натурально)
- Открытое лицо, лёгкая улыбка
- Файл: `assets/team/ekaterina.jpg`, JPG quality 85, ≤ 200 КБ
- Alt: «Екатерина Жиганова, основательница EDL OS»

---

### 19.13 Сводная карта файлов после реализации

После всех правок репо будет содержать:

```
/assets
  /hero-demo.mp4              (700 КБ, MP4 h264)
  /hero-demo.webm             (500 КБ, VP9)
  /hero-demo-poster.jpg       (80 КБ, JPG)
  /screenshots
    audit-pdf-preview.png     (≤ 80 КБ)
    tg-morning-summary.png    (≤ 80 КБ)
    tg-ai-consultant.png      (≤ 80 КБ)
    vat-map-2026.png          (≤ 80 КБ)
  /logos
    1c.svg / amocrm.svg / bitrix.svg / tinkoff.svg / getcourse.svg
  /team
    ekaterina.jpg             (≤ 200 КБ)
  /pdf
    edl-founder-os-whitepaper.pdf  (уже есть)
    edl-product-ladder.pdf         (уже есть)
    /founder-os-whitepaper/
      whitepaper.html              (уже есть, source-of-truth)

/css
  /tokens.css         (без изменений — берём как есть)
  /main-v2.css        (+ блок «UX v5» в конце, ~150 строк новых стилей)
  /components.css     (без изменений)

/index.html           (большая правка — §4, §5, §6, §7, §8)
/audit.html           (правка hero §9 + bundle-grid)
/methodology.html     (правка слепых пятен §10 + SVG)
/pricing.html         (иконки §12.1)
/faq.html             (без правок — PR #37 уже сделал)
/cases.html           (заменить placeholders на кейс)
/about.html           (фото + цитата §19.12)
```

Все файлы под лимит размера. Общий вес добавляемых ресурсов: ~ **1.5 МБ** (преимущественно MP4 + WebM). Lighthouse Performance должен остаться ≥ 85.

---

### 19.14 Финальный sanity-check перед мержем

Перед каждым мержем в main — проходить эти 8 проверок:

1. **Открыть инкогнито на iPhone-vp 375×667.** Видно ли видео/poster в первом экране? Не выходит ли кнопка primary за viewport?
2. **Открыть Lighthouse → Performance.** Score ≥ 85?
3. **Открыть DevTools → Network → Disable cache.** Сколько весит первый экран? Должно быть ≤ 1.5 МБ.
4. **Проверить prefers-reduced-motion** через DevTools → Rendering → Emulate CSS media feature. Видео исчезает, poster виден?
5. **5-секундный тест.** Дать посмотреть человеку 5 сек → закрыть → спросить «что они делают». Если «не понял» — H1 надо ещё думать.
6. **Открыть страницу без JS** (DevTools → Settings → Disable JavaScript). Hero рендерится? Кнопки видны? Email-форма виден fallback?
7. **Проверить контраст** через Lighthouse Accessibility. Все тексты gray-700 на gray-100 проходят AA?
8. **Зайти с реального телефона** (не DevTools emulation). Видео грузится? Не лагает?

Если все 8 — ✅, можно мержить.

---

_Конец §19. Документ финален и согласован._

_Версия документа: 2.0 (с visual specs)_
_Автор: Claude Sonnet 4.6_
_Согласовано с пользователем: H1 = гибрид боль+результат, hero visual = MP4-демо, объём = аудит основных страниц, все 6 открытых вопросов закрыты (см. §16)_
_Дата: 2026-05-18_

---

## 17. Ссылки на источники

- **Репо**: <https://github.com/evzhiganova8888-hub/edl-site>
- **Прод сайт**: <https://elephantdreams.ru>
- **Прод бот**: <https://t.me/edl_os_bot>
- **API**: <https://api.elephantdreams.ru>
- **Railway**: проект `efficient-appreciation`, сервис `edl-site`
- **DNS**: REG.RU, домен `elephantdreams.ru`
- **Бот source-of-truth**: `edl-os-bot/CLAUDE.md`
- **Параллельная сессия 18.05**: `~/Downloads/EDL_Session_Summary_20260518.md`
- **Прошлые работы этой сессии**:
  - `docs/website_v4_status_2026-05-18.md`
  - `docs/backend_widget_deploy_2026-05-18.md`
  - `docs/dns_setup_api_subdomain_2026-05-18.md`

---

## 18. Глоссарий

| Термин | Что значит |
|---|---|
| **EDL OS** | Бренд продукта. **E**lephant **D**reams **L**ab **O**perating **S**ystem. |
| **Founder OS Score** | Mini-Чекап. 12 вопросов, бесплатно, Score 0–100. Lead-magnet. |
| **Бизнес-чекап** | Базовый платный продукт. 9 000 ₽ Base / 14 000 ₽ Plus. 20 вопросов в боте, PDF за 24ч. |
| **НДС-карта 2026** | Часть PDF-чекапа: какие из контрактов клиента под риском из-за ФЗ 425. |
| **MCP** | Model Context Protocol (Anthropic). Open source сервер, который даёт Score внутри Claude Desktop. |
| **CRAFT** | Методология осознанного выбора (Центр CRAFT, школа инноваций ИКРА). |
| **AI Fluency** | Рамка от Anthropic + UCC + Ringling — когда отдавать ИИ, когда оставить человеку. |
| **5-секундный тест** | UX-методика: показать страницу на 5 сек, спросить «что они делают». Источник: NN/g. |
| **ICP** | Ideal Customer Profile — целевой сегмент бизнеса. |
| **NDA до 22.05** | Соглашение с клиентом Vitaconsult — раскрытие имени только после 22.05.2026. |

---

_Версия документа: 1.0_
_Автор: Claude Sonnet 4.6_
_Согласовано с пользователем: H1 = гибрид боль+результат, hero visual = MP4-демо, объём = аудит основных страниц_
_Дата: 2026-05-18_
