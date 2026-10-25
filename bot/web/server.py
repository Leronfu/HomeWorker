"""Встроенный асинхронный веб-сервер на aiohttp для Telegram Mini App."""

import logging
import os
from typing import Optional

from aiohttp import web
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import config
from bot.web.routes import (
    handle_auth_me,
    handle_claim_topic,
    handle_clear_schedule,
    handle_create_homework,
    handle_create_reports_batch,
    handle_delete_homework,
    handle_delete_reports_batch,
    handle_get_homework,
    handle_get_reports_batches,
    handle_get_schedule,
    handle_get_subjects,
    handle_health,
    handle_publish_reports_batch,
    handle_rollover_schedule,
    handle_unclaim_topic,
    handle_update_homework,
    handle_update_schedule_day,
    options_handler,
)

logger = logging.getLogger(__name__)

BOT_KEY: web.AppKey[Optional[Bot]] = web.AppKey("bot", Optional[Bot])
SCHEDULER_KEY: web.AppKey[Optional[AsyncIOScheduler]] = web.AppKey("scheduler", Optional[AsyncIOScheduler])


def create_web_app(bot: Optional[Bot] = None, scheduler: Optional[AsyncIOScheduler] = None) -> web.Application:
    """Создание и конфигурирование aiohttp Web Application."""
    app = web.Application()
    app[BOT_KEY] = bot
    app[SCHEDULER_KEY] = scheduler

    # Pre-flight CORS для всех путей API
    app.router.add_route("OPTIONS", "/api/{tail:.*}", options_handler)

    # REST API маршруты
    app.router.add_get("/api/health", handle_health)
    app.router.add_get("/api/me", handle_auth_me)
    app.router.add_post("/api/auth", handle_auth_me)
    app.router.add_get("/api/subjects", handle_get_subjects)

    # Расписание
    app.router.add_get("/api/schedule", handle_get_schedule)
    app.router.add_post("/api/schedule", handle_update_schedule_day)
    app.router.add_post("/api/schedule/rollover", handle_rollover_schedule)
    app.router.add_post("/api/schedule/clear", handle_clear_schedule)

    # Домашнее задание
    app.router.add_get("/api/homework", handle_get_homework)
    app.router.add_post("/api/homework", handle_create_homework)
    app.router.add_put("/api/homework/{id}", handle_update_homework)
    app.router.add_delete("/api/homework/{id}", handle_delete_homework)

    # Доклады
    app.router.add_get("/api/reports/batches", handle_get_reports_batches)
    app.router.add_post("/api/reports/batches", handle_create_reports_batch)
    app.router.add_delete("/api/reports/batches/{id}", handle_delete_reports_batch)
    app.router.add_post("/api/reports/batches/{id}/publish", handle_publish_reports_batch)
    app.router.add_post("/api/reports/topics/{id}/claim", handle_claim_topic)
    app.router.add_post("/api/reports/topics/{id}/unclaim", handle_unclaim_topic)

    # Раздача статических файлов веб-приложения (HTML, CSS, JS)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    web_dir = os.path.join(project_root, "web")
    if os.path.exists(web_dir):
        # Отдаем index.html при обращении к корню
        async def index_handler(request: web.Request) -> web.FileResponse:
            index_path = os.path.join(web_dir, "index.html")
            if os.path.exists(index_path):
                return web.FileResponse(index_path)
            return web.Response(text="Web App UI is being initialized...", content_type="text/html")

        app.router.add_get("/", index_handler)
        app.router.add_static("/static/", path=web_dir, name="static")

    return app


async def start_web_server(
    bot: Optional[Bot] = None,
    scheduler: Optional[AsyncIOScheduler] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> web.AppRunner:
    """Асинхронный запуск встроенного веб-сервера."""
    app = create_web_app(bot, scheduler)
    runner = web.AppRunner(app)
    await runner.setup()

    srv_host = host or config.WEB_HOST
    srv_port = port or config.WEB_PORT
    site = web.TCPSite(runner, srv_host, srv_port)
    await site.start()

    logger.info("Встроенный веб-сервер Mini App запущен на http://%s:%s", srv_host, srv_port)
    return runner
