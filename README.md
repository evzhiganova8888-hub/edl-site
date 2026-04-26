# EDL · Сайт · v1.0

Статический сайт Elephant Dreams Lab. HTML/CSS/JS без фреймворков. Все файлы в корне репозитория для простоты загрузки через веб-интерфейс GitHub.

---

## Файлы

### Сайт

```
index.html              ← Главная (11 блоков)
sprint.html             ← AI Operations Sprint
diagnostic.html         ← Диагностика
404.html                ← Кастомная 404
styles.css              ← Все стили
main.js                 ← Логика (FAQ, modal, аналитика)
sitemap.xml
robots.txt
CNAME
```

### Бренд-ассеты

```
logo.svg                ← Symbol mark V2 (для digital)
logo-wordmark.svg       ← Wordmark V6 (для PDF и презентаций)
favicon.svg             ← Иконка вкладки (исходник для всех PNG-вариантов)
og-image.svg            ← Open Graph 1200×630 (исходник для PNG)
```

### Документы

```
README.md               ← Этот файл
BRAND_GUIDELINES.md     ← Правила использования бренда
LAUNCH_CHECKLIST.md     ← Чек-лист перед запуском
MAINTENANCE_GUIDE.md    ← Как поддерживать сайт
```

---

## Что сделать перед запуском

Идти строго по `LAUNCH_CHECKLIST.md` сверху вниз. Главные блоки:

1. **Контент** — заменить плейсхолдеры (роли в Точке/Додо, ссылки, посты в TG)
2. **Визуальные ассеты** — конвертировать SVG → PNG (OG-image, favicon-варианты, скриншоты системы)
3. **Аналитика** — раскомментировать блок Метрики, подставить реальный счётчик
4. **Технический ревью** — Lighthouse, кросс-браузерный тест, mobile
5. **Домен** — DNS на elephantdreams.ru

---

## Деплой — короткая версия

1. На GitHub: создать пустой репозиторий `edl-site` (Public)
2. `Add file → Upload files` → перетащить **все файлы** из распакованной папки
3. Commit changes
4. `Settings → Pages → Source: Deploy from branch → main → / (root) → Save`
5. Через 1–2 минуты сайт по `https://USERNAME.github.io/edl-site/`

Подключение домена `elephantdreams.ru` — см. `LAUNCH_CHECKLIST.md` блок 7.

---

## Локальный просмотр (если нужно)

```bash
cd edl-site
python3 -m http.server 8000
# открыть http://localhost:8000
```

Двойным кликом по `index.html` — **не** работает. Браузер блокирует CSS по `file://`.

---

## Логотип-система — коротко

В EDL **два логотипа**:

- **V2 (Symbol mark)** — `logo.svg`. Круг с симметричной дугой. **Для digital**: сайт, бот, favicon
- **V6 (Wordmark)** — `logo-wordmark.svg`. Только буквы «EDL». **Для печати и презентаций**: PDF, Keynote, визитки

Полные правила — в `BRAND_GUIDELINES.md`.

---

**Версия:** 1.0  
**Дата:** 26 апреля 2026
