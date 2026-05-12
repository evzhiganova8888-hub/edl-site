#!/usr/bin/env bash
# Удобный wrapper для регрессии v3.1.
#
# Автоматически:
# - создаёт .venv-regression если нет
# - ставит минимум deps (4 пакета, ~20 МБ)
# - проверяет ANTHROPIC_API_KEY (через .env или Railway CLI или текущий shell)
# - запускает регрессию
#
# Запуск:
#   ./tests/regression.sh smoke      # 10 кейсов × T=0.0, ~30 ₽, 1 мин
#   ./tests/regression.sh critical   # syco + adv × 3 T, ~80 ₽, 3 мин
#   ./tests/regression.sh full       # 28 × 3 T, ~150-300 ₽, 5-10 мин
#
# С Railway env (рекомендуется — не нужно класть ключ локально):
#   railway run ./tests/regression.sh smoke

set -e

MODE="${1:-smoke}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_ROOT/.venv-regression"
REQ_FILE="$SCRIPT_DIR/requirements-regression.txt"

cd "$PROJECT_ROOT"

# 1. Проверяем Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 не найден. Установи: brew install python@3.12"
    exit 1
fi

# 2. Создаём venv если нет
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Создаю .venv-regression и ставлю deps (один раз, ~30 сек)..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install -q --upgrade pip
    "$VENV_DIR/bin/pip" install -q -r "$REQ_FILE"
    echo "✅ Готово."
fi

# 3. Активируем venv
source "$VENV_DIR/bin/activate"

# 4. Подтягиваем .env если есть, и не задано из shell/Railway
if [ -z "$ANTHROPIC_API_KEY" ] && [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

# 5. Проверяем ключ
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo ""
    echo "ERROR: ANTHROPIC_API_KEY не задан."
    echo ""
    echo "Варианты как задать:"
    echo ""
    echo "A. Через Railway CLI (рекомендуется — без копирования ключа):"
    echo "    brew install railway"
    echo "    railway login && railway link"
    echo "    railway run ./tests/regression.sh $MODE"
    echo ""
    echo "B. Локально через .env:"
    echo "    echo 'ANTHROPIC_API_KEY=sk-...' >> .env"
    echo "    echo 'ANTHROPIC_BASE_URL=https://api.proxyapi.ru/anthropic' >> .env"
    echo "    ./tests/regression.sh $MODE"
    exit 1
fi

# 6. Добавляем src в PYTHONPATH (без полного pip install -e .)
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"

case "$MODE" in
    smoke)
        echo "🚬 Smoke-режим: 10 кейсов × T=0.0 (~30 ₽, 1 мин)"
        python tests/run_regression_v3_1.py --smoke
        ;;
    critical)
        echo "🔴 Critical: syco + adv × 3 T (~80 ₽, 3 мин)"
        python tests/run_regression_v3_1.py --critical
        ;;
    full)
        echo "🎯 Полный прогон: 28 × 3 T = 84 вызова (~150-300 ₽, 5-10 мин)"
        python tests/run_regression_v3_1.py
        ;;
    *)
        echo "Usage: $0 {smoke|critical|full}"
        exit 2
        ;;
esac
