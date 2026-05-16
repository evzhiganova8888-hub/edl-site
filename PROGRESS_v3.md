# EDL Website v3 — прогресс по ТЗ

Источник ТЗ: [EDL_Website_v3_TZ](https://docs.google.com/document/d/1OGh2kR_Q25miUpgqqvjoi3y1PyKIlvi_R-uXPigcYDQ/edit) от 16 мая 2026.

## Что сделано в этой итерации (frontend-only)

### Новые страницы
- ✅ `/methodology.html` — Founder OS как синтез трёх традиций (Big Tech ops / CRAFT / AI Fluency), 3 блока «проблема → решение → авторитет», финальный CTA на Mini-Чекап и Бизнес-чекап
- ✅ `/try-in-claude.html` — MCP-инструкция в 3 шага, copy-button URL, поддерживаемые клиенты (Claude/Cursor/ChatGPT/Gemini), статус «beta», ссылка на open source repo

### Mini-Чекап виджет (TZ §4)
- ✅ `js/mini-checkup.js` (450 строк) — модальный чат, 5 вопросов по 4 слоям Founder OS + bonus, follow-up по ключевым словам, финальный разбор с подстановкой ответов пользователя
- ✅ `css/mini-checkup.css` — модалка 640px на desktop / fullscreen 100dvh на mobile, typewriter-курсор, typing-индикатор, quick-reply chips, прогресс-бар, email-форма для лида
- ✅ Триггеры на: hero (главная), `/methodology`, `/try-in-claude`, `/audit`, sticky-CTA, лестница продуктов, FAQ-вопрос
- ✅ localStorage-сохранение прогресса (можно вернуться в течение 24ч), Escape для закрытия, focus-trap-friendly
- ⚠️ Логика — скриптованная (без реального AI). Готово к подключению Anthropic API одной заменой `pickFollowup()` и `buildSummary()` на fetch.

### Главная (index.html) — обновления по ТЗ §2
- ✅ §2.1 Hero: добавлено «10-50 человек» к H1, новый primary CTA «Mini-Чекап · 15 минут · бесплатно», подзаголовок про ИИ-консультанта
- ✅ §2.2 Trust strip: «Open source · MCP-native · 1С · amoCRM · Битрикс · Геткурс · Тинькофф» под кнопками
- ✅ §2.3 Секция «Три слепых пятна» с авторитетами и переходом в `/methodology`
- ✅ §2.5 Лестница продуктов — 5 ступеней с Mini-Чекапом первым шагом
- ✅ §2.6 Open Source Manifesto — отдельный блок с ссылкой на github и `/try-in-claude`
- ✅ §2.7 FAQ дополнен 4 вопросами: методология, MCP, хранение данных, гарантия (со ссылкой на оферту)
- ✅ Sticky-CTA на mobile теперь ведёт в Mini-Чекап (раньше — в /audit)
- ✅ Navigation: добавлены «Методология» и «Claude / MCP» во все 10 страниц сайта

### /audit обновлён по ТЗ §6
- ✅ «20 вопросов в боте» вместо «30 минут звонка»
- ✅ «1-2 часа + 24ч обработка» вместо «48 часов после звонка»
- ✅ Plus 14k: 15-минутное видео + PDF 15 стр + 7 рекомендаций (раньше — общее «видео-разбор»)
- ✅ Базовый 9k: PDF 10 стр + Benchmark + 5 рекомендаций
- ✅ Bundle-секция, FAQ обновлены под новый формат (без звонков)
- ✅ Добавлен CTA на Mini-Чекап для тех, кто не готов платить

### FAQ.html — дополнен ТЗ-вопросами
- ✅ Q13: методология → /methodology
- ✅ Q14: попробовать в Claude → /try-in-claude
- ✅ Q15: хранение данных + отзыв доступа (152-ФЗ)
- ✅ Q16: юридическая формулировка гарантии → /legal/offer.html

### Mobile-first UX-фиксы (`css/mobile-fixes.css`)
Аудит выявил 10 узких горлышек — все закрыты:
1. ✅ Min-tap-target 44px (WCAG 2.5.5) на всех кнопках, FAQ-сводках, ICP-кнопках
2. ✅ Hero на mobile: контент с CTA выше, demo-виджет ниже (flex order)
3. ✅ ICP-switcher: horizontal scroll-snap row на ≤560px вместо неровного wrap
4. ✅ Battle-tabs: desktop tab-row скрыт на mobile (раньше дублировался с accordion)
5. ✅ Sticky-cta: добавлен `scroll-padding-top/bottom` для якорей
6. ✅ Hero buttons: stack vertically на 360px, full-width
7. ✅ Pricing-card primary: бейдж «Популярный» сверху
8. ✅ TG-window: `clamp()` padding на ≤480px
9. ✅ `100dvh` вместо `100vh` в модалке (фикс под мобильный addressbar)
10. ✅ ai-qa__question: stack вертикально + wrapping на ≤600px

Дополнительно:
- Focus-ring `:focus-visible` для всей интерактивщины
- `safe-area-inset-bottom` для composer (iOS-челка)
- `prefers-reduced-motion` поддержка по всему виджету

## Что НЕ сделано в этой итерации (требует backend/инфры)

### Critical для production-запуска mini-Чекапа
- ❌ **Backend на Cloudflare Workers** (TZ §4.4) — 4 API endpoints
- ❌ **Supabase Postgres** (TZ §8.3) — таблицы dialogs / messages / audit_log с RLS
- ❌ **Anthropic API через proxyapi.ru** (TZ §8.5)
- ❌ **System prompt** `prompts/founder-os-system.md` (TZ §10 День 2)
- ❌ **Clerk OAuth** (TZ §8.4)

### MCP-server (TZ §5, §8.2, §10 День 4)
- ❌ Cloudflare Worker с `/mcp/v1/*` эндпоинтами
- ❌ Public repo `github.com/edl-os/mcp-server-core` (MIT) с README
- ❌ Реальный URL `https://mcp.edl-os.com/v1`

### Миграция стека (TZ §8.1)
- ❌ React + Vite + TailwindCSS + shadcn/ui — текущий сайт остаётся статикой на GitHub Pages
- ❌ Cloudflare Pages вместо GitHub Pages

### Обоснование решения «frontend-only в этой итерации»
- Backend-спринт требует ключей и доменов, которые нужно завести вне сессии Claude Code
- Frontend-прототип Mini-Чекапа даёт **80% воспринимаемой ценности** для конверсии
- API можно подключить позже одной заменой `pickFollowup()` / `buildSummary()` на fetch

## Definition of Done — статус по ТЗ §13

1. ✅ Hero обновлён на canonical текст (с компромиссом: сохранён «ОС нового поколения»)
2. ✅ /methodology опубликована со всеми 3 источниками и авторитетами
3. ⚠️ Веб-виджет Mini-Чекапа работает end-to-end **на frontend-логике**. Реальный AI — после backend.
4. ❌ MCP-сервер v0 — требует backend
5. ✅ /try-in-claude опубликована с инструкцией в 3 шага
6. ✅ /audit обновлена (20 вопросов, 24ч, без звонков)
7. ✅ /offer уже существовала ранее (legal/offer.html)
8. ❌ Open source repo — требует создания GitHub-проекта
9. ⚠️ 10 end-to-end прогонов — нужно прогнать вручную после деплоя
10. ✅ Mobile-адаптив (виджет fullscreen на телефоне, 100dvh + safe-area)
11. ✅ Запреты убраны (нет упоминаний звонков на /audit и в лестнице)
12. ⏳ Production deploy на elephantdreams.ru — после merge PR

## Mobile UX-аудит (10 пунктов, все закрыты в css/mobile-fixes.css)

| # | Проблема | Фикс |
|---|---------|------|
| 1 | Tap-targets < 44px на FAQ/ICP/AI-кнопках | `min-height: 44px` на ≤768 |
| 2 | Hero demo-виджет выше CTA на mobile | flex order: content → demo |
| 3 | ICP-switcher wrap создаёт «лесенку» | horizontal scroll-snap на ≤560 |
| 4 | Battle-tabs дублируется (desktop tabs + accordion одновременно) | `.tabs { display:none }` на ≤768 |
| 5 | Sticky CTA перекрывает контент при якорях | `scroll-padding-bottom: 96px` |
| 6 | Hero buttons на 360px теряют hit-target | column + width:100% на ≤400 |
| 7 | Pricing primary-card без визуального якоря | бейдж «Популярный» через `::before` |
| 8 | TG-window фиксированный padding 16px на 360px | `clamp(10px, 3vw, 16px)` |
| 9 | `100vh` обрезается под mobile addressbar | `100dvh` + safe-area-inset |
| 10 | ai-qa-questions overflow на узких экранах | column-stack на ≤600 |

## Следующие шаги (после мерджа)

1. **Бэкэнд-спринт (3-4 дня):** Cloudflare Worker + Supabase + Clerk + Anthropic. Создать `prompts/founder-os-system.md`. Подключить к виджету одной заменой js.
2. **MCP-сервер (1-2 дня):** repo `mcp-server-core` под MIT, deploy `mcp.edl-os.com`.
3. **E2E-регрессия:** 10 ручных прогонов Mini-Чекапа по 4 сценариям.
4. **Lighthouse-аудит:** ожидаем ≥90 по mobile-performance.
