# Документация по аналитике для следующего шага (Klode)

Привет! Antigravity (я) завершил фронтенд-часть реализации по ТЗ v1.0 final. На всех страницах сайта `elephantdreams.ru` теперь есть разметка data-атрибутами и минимальный inline JS-трекер (в секции `<head>`).

Твоя задача — реализовать бэкенд для сбора и маршрутизации этих событий через Google Apps Script и связать их с нашими дашбордами.

## Как сейчас работает фронтенд
1. На каждой странице работает скрипт, который перехватывает клики по `[data-cta-type]`, `[data-segment-switch]`, `[data-battle-tab]`, `<details data-faq-id>` и загрузку страниц.
2. Скрипт формирует JSON-объект события (см. `analytics-manifest.json` для структуры).
3. События складываются в массив. Если переменная `window.EDL_ANALYTICS_ENDPOINT` пустая, события сохраняются в `localStorage('edl_events')`.
4. Если переменная заполнена, скрипт вызывает `fetch(ENDPOINT, {method:'POST', body:JSON.stringify(buffer)})` и очищает буфер.

## Что нужно сделать тебе
1. **Создать Apps Script Endpoint:** Написать скрипт с функцией `doPost(e)`, который будет принимать POST-запросы с массивом событий в формате JSON.
2. **Спарсить payload:** Развернуть батч событий и подготовить их к записи в таблицы.
3. **Запись в Marketing Dashboard:** Настроить запись всех "сырых" событий (построчно) на отдельный лист `Events Raw` в таблицу `Marketing Dashboard`.
4. **Агрегация:** Настроить на листе `Aggregated` (или аналогичном) подсчет: Visitors/week, Demo bookings, Audit-funnel с помощью `QUERY` / `COUNTIF`.
5. **Запись в Founder OS:** Для критических событий (Audit purchases, Demo bookings) настроить дублирующую запись на вкладку «📊 Метрики мая 2026» в `Founder OS by EDL`.
6. **Обновить ENDPOINT:** После деплоя скрипта, обнови переменную `window.EDL_ANALYTICS_ENDPOINT` в `<head>` всех HTML файлов на полученный URL веб-приложения Apps Script (или скажи, куда мне его вставить).

## Дашборды
Ссылки на нужные дашборды:
- Founder OS by EDL: `12CbmD-plyZRlA3OWxNpjJdFRGaTl3jEs-XMnt8C924E`
- Marketing Dashboard: `1ScFfCFZxdoNtxdF4pkOVU8STKgQbUn_sfmhUtnbUIis`
- Delivery Board: `1iX_OAJGkk5oaDCemt3CRo6GdEM0HjRDeWVF2XUGT0PI`
- Финансист: `18j3dUPInDR0ZPIMh14i1FDGFYizfH2davk-SwE7bg_s`

## Edge Cases для обработки
- Переполнение `localStorage` (если endpoint отвалится).
- CORS-политики при вызове Apps Script (не забудь включить доступ для всех, включая анонимных пользователей при деплое).
- Дублирование событий при повторных отправках (возможно, стоит добавить UUID каждому событию на бэкенде или фронте).

Удачи!
