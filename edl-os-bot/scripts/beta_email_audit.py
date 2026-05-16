"""Резервный скрипт: экспорт email'ов беты 12–19 мая напрямую из БД.

Запуск: python -m scripts.beta_email_audit --since 2026-05-12 --until 2026-05-19
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from src.core.config import settings
from src.db.models import Application, User
from src.db.session import async_session_factory


async def run(since: datetime, until: datetime, output: str) -> None:
    factory = async_session_factory()
    async with factory() as session:
        stmt = (
            select(User, Application)
            .outerjoin(Application, Application.user_id == User.id)
            .where(User.created_at >= since)
            .where(User.created_at <= until)
            .order_by(User.created_at)
        )
        rows = (await session.execute(stmt)).all()

    seen: set[int] = set()
    count = 0
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "telegram_id", "telegram_username", "first_name", "last_name",
            "email", "company_name", "segment", "quiz_score",
            "created_at", "has_application", "application_status",
            "consent_marketing_given_at",
        ])
        for u, app in rows:
            if u.id in seen:
                continue
            seen.add(u.id)
            email = u.email if u.consent_marketing_given_at else ""
            writer.writerow([
                u.telegram_id, u.telegram_username or "",
                u.first_name or "", u.last_name or "",
                email, u.company_name or "",
                u.segment or "", u.quiz_score or "",
                u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
                "yes" if app else "no",
                app.status if app else "",
                u.consent_marketing_given_at.strftime("%Y-%m-%d") if u.consent_marketing_given_at else "",
            ])
            count += 1

    print(f"Exported {count} unique users to {output}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Beta email audit export")
    parser.add_argument("--since", default="2026-05-12", help="Start date YYYY-MM-DD")
    parser.add_argument("--until", default="2026-05-19", help="End date YYYY-MM-DD")
    parser.add_argument("--output", default="beta_emails.csv", help="Output CSV path")
    args = parser.parse_args()

    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    until = datetime.fromisoformat(args.until).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    asyncio.run(run(since, until, args.output))


if __name__ == "__main__":
    main()
