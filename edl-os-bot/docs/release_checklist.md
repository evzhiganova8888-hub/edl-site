# Release Checklist — EDL OS Bot

> Проходить перед каждым merge в `main` и деплоем в Railway production.

---

## Перед созданием PR

- [ ] `pytest -v --tb=short` — 0 failed, 0 errors
- [ ] `pytest tests/test_pd_sanitize.py tests/test_scope_guard.py tests/test_admin_auth.py tests/test_admin_session.py -v` — security-тесты зелёные
- [ ] `python -m mypy edl-os-bot/src --ignore-missing-imports` — нет новых type errors (если mypy настроен)
- [ ] Если добавили новые env-переменные — `.env.example` обновлён
- [ ] Если добавили миграцию — Alembic revision в `migrations/versions/`, `downgrade()` реализован
- [ ] `grep -E '^\.env' edl-os-bot/.gitignore` — `.env` в gitignore
- [ ] `mcp__github__run_secret_scanning` — нет закоммиченных секретов
- [ ] Диф PR минимален и понятен (нет случайных файлов/изменений форматирования)

## После merge и триггера Railway-деплоя

- [ ] Railway → `edl-site` → Deployments → последний → **Active** (не Failed)
- [ ] Healthcheck зелёный
- [ ] В логах: `Polling started` (или `Webhook set to ...`)
- [ ] `GET /health` → 200 `{"status":"ok"}`
- [ ] Release-фаза (Procfile `release:`) отработала: `alembic upgrade head` — no errors
- [ ] `SELECT version_num FROM alembic_version` = ожидаемой последней миграции

## Smoke-test после деплоя (минимум)

- [ ] `/start` → меню появляется, запись в `users` создана
- [ ] `/admin_login <BOT_ADMIN_ACCESS_KEY>` → `✅ Авторизованы`
- [ ] Один шаг FSM Чекапа → бот отвечает, FSM продвигается
- [ ] В `bot_errors` нет новых записей за последние 15 минут:
  ```sql
  SELECT COUNT(*) FROM bot_errors WHERE created_at > now() - interval '15 minutes';
  ```

## Перед мержем в main (Gate)

- [ ] PR не draft (убрать draft статус явно)
- [ ] Все review-комментарии закрыты или имеют «accept» пометку
- [ ] Евгения подтвердила merge (явное «ok»)

---

> Обновлять этот файл при добавлении новых типов тестов или инфра-зависимостей.
