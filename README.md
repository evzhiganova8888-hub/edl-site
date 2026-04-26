# EDL · Сайт · v1.0

Статический сайт Elephant Dreams Lab. HTML/CSS/JS без фреймворков. Предназначен для деплоя на GitHub Pages с привязкой к домену `elephantdreams.ru`.

---

## Что в этой папке (текущее состояние)

```
edl-site/
├── index.html              ✅ Главная страница (готова, 11 блоков + footer)
├── assets/
│   ├── styles.css          ✅ Все стили
│   └── main.js             ✅ Вся логика (header, FAQ, modal, аналитика)
└── README.md               ✅ Этот файл
```

---

## Что ещё в работе (следующая итерация)

```
├── sprint.html             ⏳ Страница флагман-спринта
├── diagnostic.html         ⏳ Страница диагностики
├── 404.html                ⏳ Кастомная 404
├── en/
│   ├── index.html          ⏳ EN-версия главной (минимум)
│   └── sprint.html         ⏳ EN /sprint
├── sitemap.xml             ⏳
├── robots.txt              ⏳
├── CNAME                   ⏳
└── assets/
    ├── img/                ⏳ logo, favicons, og-image, screenshots
    ├── video/              ⏳ system-demo.mp4
    └── fonts/              ⏳ self-hosted woff2 (optional, для прода)
```

---

## Как посмотреть локально

Самый быстрый способ:

```bash
cd edl-site
python3 -m http.server 8000
```

Открыть в браузере: `http://localhost:8000`

Альтернативно — VS Code с расширением **Live Server**, или любой статический сервер.

> ⚠️ Просто открывать `index.html` двойным кликом — НЕ работает. Браузер блокирует загрузку CSS/JS по `file://` протоколу. Нужен HTTP-сервер.

---

## Что нужно подставить перед релизом

В файлах есть несколько плейсхолдеров. Найти и заменить:

| Что | Где | На что заменить |
|---|---|---|
| `YOUR_COUNTER_ID` | `index.html`, `assets/main.js` | Реальный ID счётчика Yandex.Metrica |
| `https://t.me/ed_studio` | везде | Реальная ссылка на TG-канал EDL |
| `hello@elephantdreams.ru` | `index.html` (footer) | Реальный email для контактов |
| `[Здесь будет 1–2 предложения про конкретные роли]` | `index.html` блок 07 | Конкретный текст про роли в Точке/Додо/ДОМ.ру/ВШЭ |
| `[Пост 1, 2, 3]` | `index.html` блок 10 | Тексты-превью последних 3 постов TG-канала |
| Скриншот системы (placeholder в hero) | `index.html` блок 01 | Реальный скриншот утренней сводки EDL — заменить `<div class="hero__visual-placeholder">` на `<img>` или `<video>` |
| Скринкаст / скриншоты CRM (placeholder в proof) | `index.html` блок 02 | Реальный скринкаст или 3 статичных скриншота |

Проще всего — открыть файлы и сделать поиск-и-замену по перечисленным строкам.

---

## Подключение Yandex.Metrica

1. Зарегистрировать счётчик на [metrika.yandex.ru](https://metrika.yandex.ru)
2. В `index.html` раскомментировать блок `<!-- Yandex.Metrica counter -->` в `<head>`
3. Заменить `YOUR_COUNTER_ID` на реальный ID счётчика (число)
4. В `assets/main.js`, в самом верху, найти переменную `METRICA_ID` и подставить тот же ID
5. В кабинете Метрики настроить цели (см. ниже)

### Цели в Метрике

Создать четыре JavaScript-цели:

| ID цели | Название |
|---|---|
| `cta_demo_click` | Клик на кнопку «Записаться на демо» |
| `cta_calendly_open` | Открыт Calendly modal |
| `scroll_50`, `scroll_75`, `scroll_100` | Глубина скролла |
| `outbound_click` | Клик на внешнюю ссылку |
| `faq_open` | Открыт FAQ-вопрос |

Эти события автоматически отправляются из `main.js` — нужно только зарегистрировать их в кабинете.

---

## Как добавлять/менять контент

### Менять текст на главной

Открыть `index.html`, найти нужный блок (они комментариями разделены: `<!-- ───── 01 · Hero ───── -->` и т.д.), править текст внутри тегов.

### Менять цвета

Все цвета — в `assets/styles.css` в блоке `:root` (раздел 2 · TOKENS). Менять там, не в компонентах.

### Менять размер шрифта

Тоже в `:root`. Используются `clamp()` для fluid-типографики (адаптируется к размеру экрана автоматически).

### Добавить блок на главную

Скопировать паттерн любой существующей секции:

```html
<section class="section">
  <div class="container">
    <div class="section-header">
      <span class="eyebrow">XX · Название</span>
      <h2>Заголовок</h2>
      <p class="lead">Подзаголовок</p>
    </div>
    <!-- контент -->
  </div>
</section>
```

Для тёмной секции добавить `section--dark`. Для тонированной — `section--tinted`.

---

## Деплой на GitHub Pages

Делается один раз, потом каждый push в main → автообновление сайта.

### Шаг 1. Создать репозиторий на GitHub

Например, `elephant-dreams/site` или `evzhiganova/edl-site`. Public.

### Шаг 2. Запушить файлы

```bash
cd edl-site
git init
git add .
git commit -m "Initial site"
git remote add origin git@github.com:USERNAME/REPO.git
git branch -M main
git push -u origin main
```

### Шаг 3. Включить GitHub Pages

В репозитории: Settings → Pages → Source: Deploy from a branch → Branch: `main`, folder: `/ (root)` → Save.

Через 1–2 минуты сайт будет доступен по `https://USERNAME.github.io/REPO/`.

### Шаг 4. Привязать домен `elephantdreams.ru`

1. Создать в корне репозитория файл `CNAME` с одной строкой:
   ```
   elephantdreams.ru
   ```

2. У регистратора домена настроить DNS:

   **A-записи** (для apex-домена `elephantdreams.ru`):
   ```
   185.199.108.153
   185.199.109.153
   185.199.110.153
   185.199.111.153
   ```

   **CNAME-запись** (для `www`):
   ```
   www  →  USERNAME.github.io
   ```

3. После того как DNS пропишется (1–24 часа), в Settings → Pages включить «Enforce HTTPS».

4. Проверить: `https://elephantdreams.ru` открывается, HTTPS работает.

---

## Шрифты

Сейчас в `index.html` подключены **Inter** и **JetBrains Mono** через Google Fonts CDN. Это работает, но имеет два минуса для прода:

1. Google Fonts иногда медленнее в РФ
2. Inter — хороший шрифт, но **Geist** (от Vercel) вписывается в дизайн-систему лучше — у него характерные геометрические формы

### Переход на self-hosted Geist + Inter (опционально, для v1.1)

1. Скачать Geist: [github.com/vercel/geist-font/releases](https://github.com/vercel/geist-font/releases) — забрать `Geist-Regular.woff2`, `Geist-Medium.woff2`, `Geist-SemiBold.woff2`, `Geist-Bold.woff2`, `GeistMono-Regular.woff2`
2. Скачать Inter: [rsms.me/inter/](https://rsms.me/inter/) — забрать `Inter-Regular.woff2`, `Inter-Medium.woff2`, `Inter-SemiBold.woff2`
3. Положить всё в `assets/fonts/`
4. В `assets/styles.css` добавить в самое начало `@font-face` декларации для каждого шрифта
5. В `index.html` убрать ссылку на Google Fonts и раскомментировать `<link rel="preload">` теги

После этого сайт грузится быстрее и не ходит в Google. Это улучшение, не блокер для запуска.

---

## Где живут какие части

| Хочу поправить | Иду в |
|---|---|
| Текст главной | `index.html` |
| Цвета | `assets/styles.css` → `:root` |
| Типографику (размеры, шрифты) | `assets/styles.css` → `:root` |
| Стили компонентов (кнопки, карточки) | `assets/styles.css` → разделы 6, 12, 16 и т.д. |
| Header / footer / nav | `index.html` (повторить на каждой странице) |
| Логику FAQ / меню / модала | `assets/main.js` |
| Аналитику (события) | `assets/main.js` секция 5 |
| URL Calendly | `index.html` (атрибут `data-url` у `.calendly-inline-widget`) |
| Подключение Метрики | `index.html` (раскомментировать блок), `assets/main.js` (переменная `METRICA_ID`) |

---

## Тестирование перед релизом

Пройти этот чек-лист:

- [ ] Открыть в Chrome, Firefox, Safari — везде работает
- [ ] Открыть на iPhone (реальный или DevTools responsive) — нормально читается, кнопки не маленькие
- [ ] Кликнуть «Записаться на демо» — модал открывается, Calendly грузится
- [ ] Закрыть модал по ESC, по клику на overlay, по кнопке × — работает
- [ ] Открыть FAQ-вопрос — раскрывается, при открытии другого предыдущий закрывается
- [ ] Меню на мобильном — гамбургер открывает/закрывает, ссылки работают
- [ ] Скролл — header при скролле получает blur-фон
- [ ] Lighthouse на главной — Performance > 85, Accessibility > 95, SEO > 95 (Performance может быть ниже, пока шрифты с Google Fonts CDN)
- [ ] Console — нет красных ошибок (предупреждения от Calendly допустимы)

---

## Что НЕ делать

- ❌ Не трогать `:root` без понимания, что меняется (там все токены — изменение каскадирует на весь сайт)
- ❌ Не использовать `localStorage` / `sessionStorage` — на статике без бэкенда это создаёт сложность; данные пользователей в любом случае идут через Calendly
- ❌ Не добавлять JS-фреймворки. Если нужно что-то динамическое — обсудить отдельно
- ❌ Не заменять placeholder-блоки на stock-фото или AI-сгенерированные изображения. Только реальные скриншоты и реальные фото (см. design-system, раздел 6)

---

## Контакты разработки

Любые вопросы по коду / архитектуре / правкам — в чат проекта в Telegram.

---

**Версия документа:** 1.0  
**Последнее обновление:** 26 апреля 2026
