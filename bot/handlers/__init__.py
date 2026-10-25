"""Обработчики сообщений и команд бота."""

from bot.handlers.admin_schedule import router as admin_schedule_router
from bot.handlers.schedule import router as schedule_router
from bot.handlers.start import router as start_router

__all__ = [
    "start_router",
    "schedule_router",
    "admin_schedule_router",
]
