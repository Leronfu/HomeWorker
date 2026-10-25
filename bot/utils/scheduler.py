"""Планировщик фоновых задач (APScheduler) для бота."""

import logging
from typing import Optional
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import config
from bot.database import copy_next_to_current_week

logger = logging.getLogger("Scheduler")

# Инициализируем асинхронный планировщик задач по московскому времени (МСК)
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


async def rollover_weekly_schedule(bot: Optional[Bot] = None) -> None:
    """Автоматический перенос расписания со следующей недели на текущую.
    
    Срабатывает каждую субботу ровно в 15:00 (МСК).
    Копирует расписание из 'next' в 'current', очищает 'next' и уведомляет старост.
    """
    logger.info("Запуск субботнего авто-переноса расписания...")
    try:
        await copy_next_to_current_week(config.DB_PATH)
        logger.info("Расписание успешно скопировано из 'next' в 'current'. 'next' очищено.")

        # Уведомляем администраторов (старост)
        if bot and config.ADMIN_IDS:
            notification_text = (
                "📢 <b>Плановое обновление расписания!</b>\n\n"
                "Расписание следующей недели автоматически перенесено на текущую.\n"
                "Слот «Следующая неделя» очищен и готов к новому заполнению старостой."
            )
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(chat_id=admin_id, text=notification_text)
                except Exception as send_err:
                    logger.warning("Не удалось отправить уведомление старосте %s: %s", admin_id, send_err)
    except Exception as err:
        logger.error("Критическая ошибка при переносе расписания: %s", err, exc_info=True)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Регистрация задач в планировщике и привязка экземпляра бота."""
    # Задача: каждую субботу в 15:00 переносить расписание
    scheduler.add_job(
        rollover_weekly_schedule,
        trigger="cron",
        day_of_week="sat",
        hour=15,
        minute=0,
        args=[bot],
        id="weekly_schedule_rollover",
        replace_existing=True,
    )
    logger.info("Задача еженедельного обновления расписания (сб 15:00 МСК) успешно зарегистрирована в планировщике.")
    return scheduler
