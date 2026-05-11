"""Тестовая конфигурация — выставляем безопасные env для unit-тестов."""
import os
import sys
from pathlib import Path

os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("ENVIRONMENT", "test")

# Чтобы импорты `from src...` работали при `pytest` из корня проекта.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
