# Railway → Webhook mode: пошаговая инструкция

> Адресат: Евгения (или Иван). Время выполнения: 5 минут.
> Контекст: чинит P0 баг «menu + error» (QA-аудит 2026-05-17).

---

## Зачем

Сейчас бот на Railway работает в **polling mode** (`WEBHOOK_BASE_URL` не задан).
При каждом деплое Railway запускает новый контейнер до того, как успел убить старый.
Оба контейнера одновременно вызывают Telegram `getUpdates` → **409 Conflict**:

```
telegram.error.Conflict: Conflict: terminated by other getUpdates request;
make sure that only one bot instance is running
```

Это видно в Railway logs (последний пример — 17.05.2026, 10:42:34 UTC).

**Следствие:** один и тот же `/start` от пользователя может быть обработан
дважды — один раз успешно (юзер видит меню), один раз с ошибкой (юзер видит
«Что-то пошло не так на нашей стороне»). Это и есть P0 баг.

Webhook mode полностью устраняет проблему: Telegram сам шлёт апдейты по HTTPS
на наш `/webhook`, и не важно, сколько инстанций — новый при старте просто
перезаписывает webhook URL.

---

## Что нужно сделать (5 шагов)

### Шаг 1. Узнать публичный URL сервиса

1. Railway → проект `edl-site` → сервис `edl-site` → **Settings** → **Networking**.
2. Скопировать **Public Domain** — это будет что-то вроде:
   ```
   edl-site-production.up.railway.app
   ```
   (без `https://` и без `/`).

> Если домена нет — нажать **Generate Domain**. Это бесплатно.

### Шаг 2. Сгенерировать секретный токен

В терминале на своей машине:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Скопировать результат (что-то вроде `aB3xY9_kLmNp2qRs7tUvW1z-XyZ8MnOpQrStUvWxYz0`).

Этот токен нужен, чтобы наш `/webhook` отвергал поддельные запросы (не от
Telegram). Telegram шлёт его в заголовке `X-Telegram-Bot-Api-Secret-Token`,
наш код проверяет совпадение ([src/main.py:104-108](../../src/main.py#L104)).

### Шаг 3. Выставить 2 переменные окружения в Railway

Railway → `edl-site` → сервис `edl-site` → **Variables** → **+ New Variable**:

| Имя | Значение |
|-----|----------|
| `WEBHOOK_BASE_URL` | `https://edl-site-production.up.railway.app` (из Шага 1, **с** `https://`) |
| `WEBHOOK_SECRET_TOKEN` | значение из Шага 2 |

Сохранить. Railway автоматически передеплоит сервис.

### Шаг 4. Проверить логи деплоя

Railway → `edl-site` → **Deployments** → последний → **View logs**.

Искать строку:

```
Starting in WEBHOOK mode. URL=https://edl-site-production.up.railway.app/webhook
```

Если видишь — отлично, webhook включился.

Если видишь предупреждение:

```
Starting in POLLING mode in production — Railway deployments will cause 409 Conflict...
```

— значит переменная `WEBHOOK_BASE_URL` не была подхвачена. Проверь, что
переменная в правильном сервисе, и сделай Redeploy вручную.

### Шаг 5. Проверить, что webhook действительно установлен

Сделать любую тестовую отправку `/start` боту от своего Telegram-аккаунта.

В Railway logs искать (вместо `Polling started`):

```
INFO uvicorn.access: POST /webhook HTTP/1.1 200 OK
```

Это означает, что Telegram шлёт апдейты на наш сервер, и сервер их принимает.

Дополнительно можно проверить через Telegram API напрямую:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

(подставить BOT_TOKEN из Railway → Variables → глаз).

Ожидаемый ответ:

```json
{
  "ok": true,
  "result": {
    "url": "https://edl-site-production.up.railway.app/webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "max_connections": 40,
    "ip_address": "...",
    "allowed_updates": []
  }
}
```

Поле `url` должно совпадать с тем, что мы задали в `WEBHOOK_BASE_URL` + `/webhook`.

---

## Как откатить, если что-то пошло не так

1. Railway → `edl-site` → **Variables** → удалить `WEBHOOK_BASE_URL` (или
   очистить значение).
2. Сохранить → Railway передеплоит.
3. Бот вернётся в polling mode, 409 Conflict снова появятся при деплоях, но
   бот будет отвечать.
4. Дополнительно — сбросить webhook на стороне Telegram:
   ```bash
   curl "https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook?drop_pending_updates=true"
   ```

---

## Что произойдёт при следующем деплое после включения webhook

1. Старый контейнер живёт, webhook указывает на его FastAPI (но Railway уже не
   роутит трафик к нему — старый контейнер dormant).
2. Новый контейнер стартует → `lifespan` вызывает `set_webhook(...)` с тем же
   URL (но Railway теперь роутит к новому).
3. `set_webhook` атомарно обновляет внутреннее состояние Telegram — все будущие
   апдейты идут на новый URL (фактически — Railway-балансер → новый контейнер).
4. Конфликта двух одновременных `getUpdates` нет (никто не вызывает
   `getUpdates` вообще).
5. Старый контейнер умирает по SIGTERM. Чисто.

---

## После применения

Когда выставите переменные и убедитесь, что в логах появилось
`Starting in WEBHOOK mode`, напишите «webhook включён» в чат с Claude
(или сюда). Я обновлю QA-аудит и проверю в Railway logs, что 409 Conflict
больше не появляются.
