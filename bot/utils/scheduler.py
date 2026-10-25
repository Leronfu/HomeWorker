"""Планировщик фоновых задач (APScheduler) для бота."""

import logging
from typing import Optional
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import config
import html
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
import zoneinfo
from bot.database import (
    copy_next_to_current_week,
    get_all_users,
    get_batch_by_id,
    get_pending_report_batches,
    publish_report_batch,
)

logger = logging.getLogger("Scheduler")
MSK_TZ = zoneinfo.ZoneInfo("Europe/Moscow")

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


async def broadcast_report_drop(bot: Bot, batch_id: int) -> int:
    """Массовая рассылка всем зарегистрированным пользователям о честном дропе тем докладов."""
    logger.info("Запуск массовой рассылки о дропе докладов batch_id=%s...", batch_id)
    batch = await get_batch_by_id(batch_id, config.DB_PATH)
    if not batch:
        return 0

    subj_name = batch.get("subject_name", "Предмет")
    seminar_date = batch.get("seminar_date", "—")
    users = await get_all_users(config.DB_PATH)

    broadcast_text = (
        f"🔥 <b>ВЫЛОЖЕНЫ ТЕМЫ ДОКЛАДОВ!</b> 🔥\n\n"
        f"Староста открыл запись на доклады по предмету «<b>{html.escape(subj_name)}</b>»!\n"
        f"🗓 <b>Дата семинара:</b> <code>{html.escape(seminar_date)}</code>\n\n"
        "⚡ <i>Скорее заходите в раздел «Доклады», чтобы занять тему первым!</i>"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎤 Перейти к темам докладов",
                    callback_data=f"rep_view_batch:{batch_id}",
                )
            ]
        ]
    )

    sent_count = 0
    for user in users:
        tg_id = user["telegram_id"]
        try:
            await bot.send_message(chat_id=tg_id, text=broadcast_text, reply_markup=markup)
            sent_count += 1
        except Exception as e:
            logger.debug("Не удалось доставить рассылку пользователю %s: %s", tg_id, e)

    logger.info("Рассылка о дропе #%s успешно отправлена %d пользователям.", batch_id, sent_count)
    return sent_count


async def publish_report_job(bot: Optional[Bot], batch_id: int) -> None:
    """Публикация партии докладов по наступлению назначенного случайного времени."""
    logger.info("Сработал триггер публикации докладов для batch_id=%s", batch_id)
    try:
        batch = await get_batch_by_id(batch_id, config.DB_PATH)
        if not batch:
            logger.warning("Партия докладов %s не найдена в БД.", batch_id)
            return

        if batch.get("is_published"):
            logger.info("Партия докладов %s уже была опубликована ранее.", batch_id)
            return

        # 1. Помечаем в БД как опубликованную
        await publish_report_batch(batch_id, config.DB_PATH)
        logger.info("Партия докладов %s успешно помечена как опубликованная.", batch_id)

        # 2. Массовая рассылка всем студентам учебной группы
        if bot:
            await broadcast_report_drop(bot, batch_id)

    except Exception as err:
        logger.error("Ошибка при публикации партии докладов %s: %s", batch_id, err, exc_info=True)


def schedule_report_release(bot: Bot, batch_id: int, run_datetime: datetime) -> None:
    """Добавить отложенную задачу публикации дропа докладов в планировщик."""
    job_id = f"report_batch_{batch_id}"
    scheduler.add_job(
        publish_report_job,
        trigger="date",
        run_date=run_datetime,
        args=[bot, batch_id],
        id=job_id,
        replace_existing=True,
    )
    logger.info(
        "Задача дропа докладов #%s запланирована на %s (МСК)",
        batch_id,
        run_datetime.strftime("%Y-%m-%d %H:%M:%S"),
    )


def cancel_scheduled_report_job(batch_id: int) -> bool:
    """Отменить запланированную задачу дропа в планировщике."""
    job_id = f"report_batch_{batch_id}"
    try:
        job = scheduler.get_job(job_id)
        if job:
            scheduler.remove_job(job_id)
            logger.info("Задача планировщика %s успешно удалена.", job_id)
            return True
    except Exception as e:
        logger.warning("Не удалось удалить задачу %s из планировщика: %s", job_id, e)
    return False


async def restore_pending_report_jobs(bot: Bot) -> int:
    """Восстановление отложенных задач дропов при запуске бота.
    
    Гарантирует, что запланированные доклады не потеряются при перезагрузке сервера.
    """
    pending = await get_pending_report_batches(config.DB_PATH)
    restored_count = 0
    now_msk = datetime.now(MSK_TZ)

    for b in pending:
        batch_id = b["id"]
        raw_dt = b["release_datetime_random"]
        try:
            # Парсим "YYYY-MM-DD HH:MM:SS"
            dt_parsed = datetime.strptime(raw_dt, "%Y-%m-%d %H:%M:%S").replace(tzinfo=MSK_TZ)
            if dt_parsed > now_msk:
                schedule_report_release(bot, batch_id, dt_parsed)
                restored_count += 1
            else:
                # Если время дропа уже наступило, пока бот был выключен — публикуем немедленно!
                logger.info("Время дропа #%s уже прошло (%s), выполняем публикацию...", batch_id, raw_dt)
                await publish_report_job(bot, batch_id)
                restored_count += 1
        except Exception as e:
            logger.error("Ошибка при восстановлении задачи дропа #%s: %s", batch_id, e)

    logger.info("Восстановлено запланированных дропов докладов: %d", restored_count)
    return restored_count


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
