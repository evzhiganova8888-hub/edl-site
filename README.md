# EDL OS Website

Репозиторий фронтенда сайта EDL OS (elephantdreams.ru). 
Релиз: v2 (May 2026).

## Структура сайта
- `/index.html` - Главная страница.
- `/audit.html` - Лендинг Бизнес-чекапа (9 000 ₽).
- `/pricing.html` - Полная продуктовая лестница.
- `/diagnostic.html` - Страница диагностики.
- `/sprint.html` - Страница базового продукта (Спринт).
- `/cases.html` - Кейсы клиентов.
- `/faq.html` - Расширенный FAQ.
- `/about.html` - Команда и история.
- `/quiz.html` - Старый квиз-воронка.
- `/css/` - Стили, включая `main-v2.css` с новыми компонентами.

## Локальная разработка
Для тестирования сайта поднимите локальный сервер, так как JS-модули (и аналитика) могут требовать HTTP:
```bash
python3 -m http.server 8000
```
Затем откройте `http://localhost:8000` в браузере.

## Аналитика
Сайт не использует внешних счетчиков (GA4, Metrica). 
Вся телеметрия собирается встроенным `inline-JS` трекером (см. секцию `<head>` в HTML-файлах).

- События накапливаются в `localStorage` (ключ `edl_events`).
- При наличии переменной `window.EDL_ANALYTICS_ENDPOINT` (которая будет указывать на Google Apps Script) события отправляются через `fetch` (метод POST).
- Для разметки кнопок и элементов используются атрибуты `data-cta-type`, `data-cta-location`, `data-segment-switch`, `data-battle-tab` и др.
- Полная структура событий и атрибутов описана в файле [analytics-manifest.json](./analytics-manifest.json).
- Инструкция для бэкенда (Apps Script) лежит в файле [README_for_klode.md](./README_for_klode.md).
