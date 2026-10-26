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

# На облачных серверах (Alwaysdata, Render) переменные PORT и IP имеют наивысший приоритет
cloud_port = os.getenv("PORT")
cloud_ip = os.getenv("IP")

WEB_HOST: str = cloud_ip or os.getenv("WEB_HOST") or "0.0.0.0"
raw_port = cloud_port or os.getenv("WEB_PORT") or "8080"
WEB_PORT: int = int(str(raw_port).strip())
def _resolve_web_app_url() -> str:
    """Определение внешнего HTTPS URL для Telegram Web App.

    Telegram Bot API строго требует HTTPS для кнопок WebAppInfo.
    На Alwaysdata сервис работает по адресу https://leronfu.alwaysdata.net.
    """
    raw_url = os.getenv("WEB_APP_URL", "").strip()
    if not raw_url:
        return "https://leronfu.alwaysdata.net"
    if raw_url.startswith("http://"):
        return "https://" + raw_url[7:]
    return raw_url

WEB_APP_URL: str = _resolve_web_app_url()
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads/homework").strip()

def get_safe_web_app_url() -> str:
    """Гарантированно возвращает валидный HTTPS URL для Telegram WebAppInfo."""
    url = (WEB_APP_URL or "").strip()
    if not url or not url.startswith("https://"):
        return "https://leronfu.alwaysdata.net"
    return url

def is_admin(telegram_id: int) -> bool:
    """Проверка, является ли пользователь администратором."""
    return telegram_id in ADMIN_IDS
