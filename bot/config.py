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

WEB_HOST: str = os.getenv("WEB_HOST") or os.getenv("IP") or "0.0.0.0"
raw_port = os.getenv("WEB_PORT") or os.getenv("PORT") or "8080"
WEB_PORT: int = int(str(raw_port).strip())
WEB_APP_URL: str = os.getenv("WEB_APP_URL", f"http://localhost:{WEB_PORT}").strip()

def is_admin(telegram_id: int) -> bool:
    """Проверка, является ли пользователь администратором."""
    return telegram_id in ADMIN_IDS
