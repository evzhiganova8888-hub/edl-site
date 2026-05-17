# Smoke Test Results — PR #18 feat/bot-v3.2-checkup-flow

**Date**: 2026-05-17  
**Tester**: QA automated session  
**Branch**: `feat/bot-v3.2-checkup-flow`  
**Pytest baseline**: 140 passed, 1 skipped (robokassa), 0 failed

---

## Environment

| Component | Status | Notes |
|---|---|---|
| Python 3.12.13 (.venv312) | ✅ Available | via uv |
| PostgreSQL | ❌ Not available | No Docker, no local install, port 5432 closed |
| Redis | ❌ Not available | |
| BOT_TOKEN | ❌ Not set | .env has only ANTHROPIC_API_KEY |
| Docker | ❌ Not available | |

**Conclusion**: Live smoke tests (§7) cannot be executed in this environment.  
Below: (A) static / unit-level verification results, (B) §8.3 security check results.

---

## A. Static Verification (Flows verified via tests + code review)

| Flow | Description | Verified via | Status |
|---|---|---|---|
| 7.2 Flow 1 | Quiz 12 questions, segment detection | `test_quiz.py` (7 tests), `test_segment.py` (10 tests) | ✅ PASS |
| 7.3 Flow 2 | Stub purchase, offer text, ПД consent | `test_offer.py`, `test_consent.py`, `test_payments_stub.py` | ✅ PASS |
| 7.4 Flow 3 | /checkup FSM, 20 questions, quality gate | `test_checkup_questions.py`, `test_checkup_quality.py`, `test_checkup_report.py` | ✅ PASS |
| 7.5 Flow 4 | Off-topic scope guard (6 off + 1 on-topic) | `test_scope_guard.py` (§7.5 parametrized, 25 tests total) | ✅ PASS |
| 7.6 Flow 5 | Admin rate-limit (hmac.compare_digest) | `test_admin_session.py` (5 tests) | ✅ PASS |
| 7.7 Flow 6 | /refund flow | `test_notifications.py` (refund_brief) | ✅ PASS (partial) |
| 7.8 Flow 7 | /emails_dump + /beta_summary | Code review: consent_marketing checked before export | ✅ PASS (code review) |
| 7.9 Flow 8 | /privacy + /delete_my_data | Code review: soft-delete logic in repos.py | ✅ PASS (code review) |

> Live Telegram bot flows (7.2–7.9 end-to-end) require BOT_TOKEN + PostgreSQL + Redis.  
> To run live: `docker compose up -d postgres redis && alembic upgrade head && python -m src.main`

---

## B. §8.3 Security Checks

| Check | Command | Result |
|---|---|---|
| No secrets in commits | `git log -p \| grep "BOT_ADMIN_ACCESS_KEY="` | ✅ Only empty placeholder in .env.example |
| No hardcoded tokens in src/ | `grep -rn "BOT_TOKEN\|ANTHROPIC_API_KEY" src/` | ✅ Only RuntimeError guards + pd_sanitize regex |
| callback_data ≤ 64 bytes | Grep + awk on all callback_data= | ✅ Max 25 bytes (`audit:start_purchase:plus`) |
| hmac.compare_digest used | `grep -rn "compare_digest" src/` | ✅ `admin_login.py:93` |
| Admin key not logged in plaintext | `grep -rn "admin_login" src/ \| grep "log"` | ✅ No key values in log calls |
| No raw SQL injection | `grep -rn 'text(".*\\+' src/` | ✅ Only static partial-index expressions |

---

## C. Migration Chain Verification (Task C)

**Environment**: No live PostgreSQL — static verification only.

| Check | Result |
|---|---|
| Linear chain 0001→0007 | ✅ Verified via `revision`/`down_revision` attributes |
| 0006 syntax (AST parse) | ✅ OK |
| 0007 syntax (AST parse) | ✅ OK |
| 0006 creates `admin_sessions` + checkup cols on `applications` | ✅ Matches `src/db/models.py` lines 278, 90-92 |
| 0007 creates `checkup_answers` + unique index `uq_checkup_answers_app_q` | ✅ Matches `src/db/models.py` lines 291, 305-306 |
| Both `upgrade()` + `downgrade()` present | ✅ |

> To run live: `docker compose up -d postgres && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`

---

## D. Items Requiring Live Testing

The following cannot be verified without a running bot:

| Item | Blocker |
|---|---|
| `users` table populated on /start | Need DB |
| Admin bریف arrives in ADMIN_CHAT_ID | Need BOT_TOKEN + ADMIN_CHAT_ID |
| Layer intro messages (📍📈⚙️💰) appear | Need live bot |
| PDF generation (WeasyPrint / Celery) | Need Docker stack |
| Rate-limit lockout after 3 wrong /admin_login | Need Redis |
| /refund sets status='refund_requested' | Need DB |
| /emails_dump generates CSV with consent filter | Need DB with data |

**Recommendation**: Run `docker compose up` on staging / Railway before merging to production.

---

## Summary

| Category | Status |
|---|---|
| Pytest (140 tests) | ✅ 140 passed, 1 skipped, 0 failed |
| Security §8.3 | ✅ All 6 checks passed |
| Migration chain | ✅ Verified statically |
| Live smoke tests | ⚠️ Blocked — no Docker/DB/BOT_TOKEN locally |
