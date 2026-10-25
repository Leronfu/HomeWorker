"""Конфигурация проекта и переменные окружения."""

import os
from typing import List
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
DB_PATH: str = os.getenv("DB_PATH", "homeworker.db").strip()

def _parse_admin_ids(raw_ids: str) -> List[int]:
    """Парсинг списка Telegram ID администраторов из строки."""
    admin_ids: List[int] = []
    if not raw_ids:
        return admin_ids
    for item in raw_ids.split(","):
        cleaned = item.strip()
        if cleaned.isdigit():
            admin_ids.append(int(cleaned))
    return admin_ids

ADMIN_IDS: List[int] = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))

WEB_HOST: str = os.getenv("WEB_HOST", "0.0.0.0").strip()
WEB_PORT: int = int(os.getenv("WEB_PORT", "8080").strip() or 8080)
WEB_APP_URL: str = os.getenv("WEB_APP_URL", f"http://localhost:{WEB_PORT}").strip()

def is_admin(telegram_id: int) -> bool:
    """Проверка, является ли пользователь администратором."""
    return telegram_id in ADMIN_IDS
