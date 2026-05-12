#!/usr/bin/env bash
# Удобный wrapper для регрессии v3.1.
#
# Запуск:
#   ./tests/regression.sh smoke      # 10 кейсов × T=0.0, ~30 ₽, 1 мин
#   ./tests/regression.sh critical   # syco + adv × 3 T, ~80 ₽, 3 мин
#   ./tests/regression.sh full       # 28 × 3 T, ~150-300 ₽, 5-10 мин
#
# Из репозитория:
#   cd edl-os-bot
#   ./tests/regression.sh smoke
#
# Из Railway shell (рекомендуется — все env уже есть):
#   Railway dashboard → service edl-site → Settings → Cmd palette
#   → Shell → bash tests/regression.sh smoke

set -e

MODE="${1:-smoke}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY не задан."
    echo ""
    echo "Локально: export ANTHROPIC_API_KEY=sk-... (ключ от proxyapi.ru)"
    echo "         export ANTHROPIC_BASE_URL=https://api.proxyapi.ru/anthropic"
    echo ""
    echo "Railway: запусти через Railway shell — env уже есть."
    exit 1
fi

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
