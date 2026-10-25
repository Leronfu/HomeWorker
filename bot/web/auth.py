"""Модуль аутентификации и валидации Telegram Mini App (Web App) initData."""

import hashlib
import hmac
import json
import logging
import urllib.parse
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def validate_telegram_init_data(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    """
    Валидация строки initData от Telegram Web App по алгоритму HMAC-SHA-256.
    
    Возвращает словарь данных пользователя (из поля 'user') или весь словарь полей,
    либо None, если подпись неверна или данные повреждены.
    """
    if not init_data:
        return None

    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed_data:
            return None

        received_hash = parsed_data.pop("hash")
        data_check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(parsed_data.items(), key=lambda item: item[0])
        )

        # Вычисляем секретный ключ: HMAC-SHA256("WebAppData", bot_token)
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()

        # Вычисляем контрольный хэш
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            logger.warning("Неверная контрольная сумма initData Telegram Web App")
            return None

        # Извлекаем JSON объекта user
        user_raw = parsed_data.get("user")
        if user_raw:
            user_dict = json.loads(user_raw)
            # Дополнительно передаем дату аутентификации, если она присутствует
            if "auth_date" in parsed_data:
                user_dict["auth_date"] = parsed_data["auth_date"]
            return user_dict

        return parsed_data
    except Exception as exc:
        logger.error("Ошибка при валидации initData: %s", exc)
        return None


def generate_mock_init_data(user_dict: Dict[str, Any], bot_token: str) -> str:
    """Генерация валидной строки initData для модульных тестов."""
    user_str = json.dumps(user_dict, separators=(",", ":"))
    params = {
        "auth_date": "1700000000",
        "query_id": "AAHdF6IQAAAAAN0XohD12345",
        "user": user_str,
    }
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items(), key=lambda item: item[0])
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    params["hash"] = calc_hash
    return urllib.parse.urlencode(params)
