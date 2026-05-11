"""Admin auth: проверка списка ADMIN_USER_IDS."""
import os

import pytest
from fastapi import HTTPException

from src.admin.auth import is_admin, require_admin


def test_no_admins_by_default():
    # По умолчанию ADMIN_USER_IDS пуст
    assert is_admin(99999) is False


def test_require_admin_no_header():
    with pytest.raises(HTTPException) as exc:
        require_admin(x_telegram_user_id=None)
    assert exc.value.status_code == 401


def test_require_admin_non_digit():
    with pytest.raises(HTTPException) as exc:
        require_admin(x_telegram_user_id="not-a-number")
    assert exc.value.status_code == 401


def test_require_admin_not_in_list():
    with pytest.raises(HTTPException) as exc:
        require_admin(x_telegram_user_id="12345")
    assert exc.value.status_code == 403
