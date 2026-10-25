"""Точка входа для запуска Telegram-бота учебной группы."""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import BOT_TOKEN, DB_PATH
from bot.database import init_db
from bot.handlers import admin_schedule_router, schedule_router, start_router
from bot.utils import setup_scheduler

# Настройка красивого и понятного логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("HomeWorkerBot")


async def main() -> None:
    """Основная функция инициализации и запуска бота."""
    logger.info("Запуск бота учебной группы...")

    # Проверка наличия токена
    if not BOT_TOKEN:
        logger.error(
            "ОШИБКА: Токен бота не найден! "
            "Убедитесь, что вы создали файл .env на основе .env.example и указали в нём BOT_TOKEN."
        )
        sys.exit(1)

    # 1. Инициализация базы данных SQLite
    logger.info("Инициализация базы данных SQLite: %s", DB_PATH)
    await init_db(DB_PATH)
    logger.info("База данных успешно инициализирована.")

    # 2. Инициализация экземпляров Bot и Dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # 3. Регистрация роутеров
    dp.include_router(start_router)
    dp.include_router(schedule_router)
    dp.include_router(admin_schedule_router)

    # 4. Инициализация и запуск планировщика задач (APScheduler)
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Планировщик фоновых задач APScheduler запущен.")

    # 5. Удаление вебхуков и запуск поллинга
    logger.info("Бот готов к работе и ожидает сообщений!")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("Планировщик задач остановлен.")
        await bot.session.close()
        logger.info("Работа бота завершена.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем.")
