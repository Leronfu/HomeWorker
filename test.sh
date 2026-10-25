#!/usr/bin/env bash
# Скрипт для запуска тестов бота через виртуальное окружение .venv

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -f ".venv/bin/python3" ]; then
    PYTHON=".venv/bin/python3"
else
    PYTHON="python3"
fi

"$PYTHON" -m unittest discover tests "$@"
