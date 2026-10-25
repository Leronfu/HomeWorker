from bot.handlers.admin_homework import router as admin_homework_router
from bot.handlers.admin_reports import router as admin_reports_router
from bot.handlers.admin_schedule import router as admin_schedule_router
from bot.handlers.homework import router as homework_router
from bot.handlers.schedule import router as schedule_router
from bot.handlers.start import router as start_router

__all__ = [
    "start_router",
    "schedule_router",
    "admin_schedule_router",
    "homework_router",
    "admin_homework_router",
    "admin_reports_router",
]


