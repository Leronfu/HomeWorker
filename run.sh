#!/usr/bin/env bash
# Скрипт быстрого запуска бота для старосты

cd "$(dirname "$0")" || exit 1

if [ -d ".venv" ]; then
    source .venv/bin/activate
    python3 main.py
else
    echo "⚠️ Виртуальное окружение .venv не найдено!"
    echo "Создайте его командой: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi
