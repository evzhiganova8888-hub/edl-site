# Настройка `api.elephantdreams.ru` → Railway

**Дата:** 2026-05-18
**Регистратор:** REG.RU
**Что получим:** `https://api.elephantdreams.ru` отвечает на запросы бэкенда EDL OS Bot

---

## ⚠️ Порядок шагов важен

Сначала добавляем custom domain **в Railway** (он покажет CNAME target).
Потом добавляем CNAME-запись **в REG.RU** (используя тот target).
Потом ждём DNS-пропагацию (10 мин – 2 часа) и Railway выпустит TLS-сертификат сам.

Не наоборот.

---

## Шаг 1. Railway — добавить custom domain

1. Открой [https://railway.app/dashboard](https://railway.app/dashboard)
2. Войди → выбери проект (тот, где деплоится `edl-os-bot`)
3. В списке сервисов кликни на сервис `edl-site` (или как он называется — тот, у которого URL `edl-site-production.up.railway.app`)
4. Сверху — таб **Settings**
5. Прокрути до раздела **Networking** → **Public Networking** → блок **Domains**
6. Должен быть уже один домен: `edl-site-production.up.railway.app` — это служебный
7. Нажми кнопку **+ Custom Domain**
8. Появится поле ввода → введи: `api.elephantdreams.ru`
9. Нажми **Add Domain**

10. **Railway покажет инструкцию** примерно такого вида:
    ```
    Add the following DNS record to your domain provider:

    Type:   CNAME
    Name:   api
    Value:  xxxxxxxxxx.up.railway.app   ← запиши это значение!
    ```
    Значение в поле `Value` — **скопируй его**, оно понадобится в Шаге 2.
    (Это НЕ обязательно `edl-site-production.up.railway.app` — Railway часто даёт отдельный subdomain для custom domains.)

11. Над инструкцией будет статус: **Waiting for DNS** (оранжевая плашка). Это нормально — после Шага 2 сам сменится на ✅.

**Оставь эту вкладку открытой** — будем сюда возвращаться.

---

## Шаг 2. REG.RU — добавить CNAME-запись

1. Открой [https://www.reg.ru/user/account/](https://www.reg.ru/user/account/) → войди
2. В верхнем меню: **Мои домены и услуги** (или **Domains**)
3. В списке доменов найди **elephantdreams.ru** → кликни на название
4. В левом меню (или сверху, зависит от версии интерфейса) выбери **DNS-серверы и управление зоной**
   - Если видишь надпись «Используются сторонние DNS-серверы (например, ns1.cloudflare.com)» — значит DNS не на REG.RU. **Стоп**, скажи мне — добавим запись там, где реально хостится DNS.
   - Если видишь «Используются DNS-серверы REG.RU: ns1.reg.ru, ns2.reg.ru» — продолжай ↓
5. На странице будет таблица существующих записей (A, AAAA, MX, NS, TXT и т.д.)
6. Под таблицей или сверху — кнопка **Добавить запись** (может называться **+ Добавить**, **Создать запись**)
7. В форме укажи:
   | Поле | Значение |
   |---|---|
   | **Тип записи** | `CNAME` |
   | **Subdomain / Имя / Поддомен** | `api` (БЕЗ `.elephantdreams.ru`, только `api`) |
   | **Data / Значение / Каноническое имя** | `xxxxxxxxxx.up.railway.app.` ← то, что скопировал в Шаге 1.10. **Точка в конце обязательна** (это абсолютная DNS-запись). |
   | **TTL** | `3600` (или оставь по умолчанию) |
   | **Приоритет** | оставь пустым / по умолчанию |
8. Нажми **Добавить запись** / **Сохранить**

9. Появится сообщение «Запись добавлена. Изменения вступят в силу в течение 15 минут – 24 часов» (реально обычно 10–30 минут).

---

## Шаг 3. Проверить, что DNS обновился

Жди минимум 10 минут. Потом в терминале:

```bash
dig api.elephantdreams.ru CNAME +short
```

Должен вернуть что-то вроде:
```
xxxxxxxxxx.up.railway.app.
```

Если возвращает пусто — DNS ещё не пропагировался, подожди ещё 15 минут и повтори.

Альтернатива (если нет `dig`):
```bash
nslookup api.elephantdreams.ru
```
В выводе должно быть `canonical name = xxxxxxxxxx.up.railway.app`.

Можно также онлайн-чеком: <https://dnschecker.org/#CNAME/api.elephantdreams.ru> — там видно, во всех ли зонах мира появилась запись.

---

## Шаг 4. Дождаться TLS-сертификата от Railway

Когда DNS пропагировался, Railway сам:
1. Увидит, что CNAME указывает на их серверы
2. Запросит у Let's Encrypt сертификат для `api.elephantdreams.ru`
3. Установит его

Обычно занимает **5–30 минут после того, как DNS заработал**.

Вернись на вкладку Railway → Settings → Domains. У записи `api.elephantdreams.ru` оранжевая плашка **Waiting for DNS** должна смениться на:
- ⏳ **Issuing certificate** (Railway получает TLS)
- ✅ **Active** (всё готово)

---

## Шаг 5. Финальная проверка

```bash
curl -i https://api.elephantdreams.ru/health
```

Должен вернуть:
```
HTTP/2 200
content-type: application/json

{"status":"ok","use_webhook":true,"payment_mode":"stub"}
```

Если получил 200 с JSON — **всё работает**. Можно мержить PR `claude/website-v4-updates`.

---

## Возможные проблемы

### `dig` возвращает старое значение или ничего > 1 часа
Возможно, в REG.RU есть конфликтующая A-запись `api.elephantdreams.ru → 1.2.3.4`. Зайди в таблицу DNS-записей, найди и удали любые `A` или `AAAA` записи с именем `api` (CNAME не уживается с A на одном имени).

### Railway пишет «Invalid CNAME»
Проверь, что в значении CNAME записи в REG.RU **есть точка на конце** (`xxxxx.up.railway.app.`). Без точки REG.RU добавляет `.elephantdreams.ru` к концу, получается мусор.

### `curl` возвращает 525 / 526 / certificate error
Railway ещё не успел выпустить TLS. Подожди 15 минут и повтори. Если не помогло — в Railway UI у домена будет красная плашка с диагностикой.

### `curl` возвращает 404 на `/health`
Значит DNS → Railway работает, но запрос пришёл не на тот сервис. Проверь в Railway, что custom domain привязан к сервису `edl-site` (а не к какому-то другому, если в проекте их несколько).

### `curl` возвращает CORS error из браузера
Должно работать — в `src/main.py` добавлен CORSMiddleware с `https://elephantdreams.ru` в allow_origins. Если хочешь поддержать ещё какой-то домен (`stage.elephantdreams.ru` и т.п.) — скажи, добавлю.

---

## Что делать когда всё заработает

1. **Замержить PR** `claude/website-v4-updates` в main
2. Railway сам пересоберёт контейнер (deploy ~1–2 мин), применит миграцию 0008 (`whitepaper_leads`)
3. Открыть `elephantdreams.ru` в браузере → проверить виджет (подожди 30с + проскролль 30% → виджет откроется → нажми кнопку → должен прийти ответ)
4. Открыть `elephantdreams.ru/methodology.html` → ввести email в форму whitepaper → нажать «Скачать PDF» → должен открыться PDF и **прийти TG-уведомление в админ-чат**

Если на этих шагах что-то не работает — пиши, разберёмся.
