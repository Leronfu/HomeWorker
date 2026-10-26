"""Планировщик фоновых задач (APScheduler) для бота."""

import logging
from typing import Any, Dict, List, Optional
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import config
import html
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from datetime import datetime, timedelta
import zoneinfo
from bot.database import (
    auto_assign_remaining_topics,
    cleanup_expired_homework_files,
    copy_next_to_current_week,
    get_all_admin_ids,
    get_all_users,
    get_batch_by_id,
    get_batch_topics,
    get_pending_auto_assign_batches,
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
            url = config.get_safe_web_app_url()
            starosta_markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📅 Открыть расписание в Mini App",
                            web_app=WebAppInfo(url=url),
                        )
                    ]
                ]
            )
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(chat_id=admin_id, text=notification_text, reply_markup=starosta_markup)
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
        "⚡ <i>Скорее открывайте приложение «Доклады», чтобы занять тему первым!</i>"
    )

    url = config.get_safe_web_app_url()
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎤 Открыть темы в Mini App",
                    web_app=WebAppInfo(url=url),
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


async def notify_admins_report_drop(bot: Bot, batch_id: int, db_path: Optional[str] = None) -> int:
    """Уведомление администраторов (старост) о том, что темы докладов были выложены рандомайзером."""
    logger.info("Отправка уведомления администраторам о дропе batch_id=%s...", batch_id)
    actual_db = db_path or config.DB_PATH
    batch = await get_batch_by_id(batch_id, actual_db)
    if not batch:
        return 0

    topics = await get_batch_topics(batch_id, actual_db)
    subj_name = batch.get("subject_name", "Предмет")
    seminar_date = batch.get("seminar_date", "—")
    topics_count = len(topics)

    admin_ids = await get_all_admin_ids(actual_db)
    if not admin_ids:
        logger.warning("Список администраторов пуст, уведомление о дропе некому отправить.")
        return 0

    admin_notification_text = (
        "🎲 <b>РАНДОМАЙЗЕР ВЫЛОЖИЛ РАБОТЫ!</b> 🔔\n\n"
        f"Наступило случайное время публикации докладов!\n"
        f"📚 <b>Предмет:</b> «<b>{html.escape(subj_name)}</b>»\n"
        f"🗓 <b>Дата семинара:</b> <code>{html.escape(seminar_date)}</code>\n"
        f"📝 <b>Количество выложенных тем:</b> <code>{topics_count}</code>\n\n"
        "📢 Уведомление разослано студентам группы. Запись на доклады открыта!"
    )

    url = config.get_safe_web_app_url()
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👁 Открыть темы в Mini App",
                    web_app=WebAppInfo(url=url),
                )
            ]
        ]
    )

    sent_count = 0
    for adm_id in admin_ids:
        try:
            await bot.send_message(chat_id=adm_id, text=admin_notification_text, reply_markup=markup)
            sent_count += 1
        except Exception as err:
            logger.warning("Не удалось отправить уведомление о дропе администратору %s: %s", adm_id, err)

    logger.info("Уведомление о дропе #%s отправлено %d администраторам.", batch_id, sent_count)
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
            # 3. Персональное уведомление администраторам о состоявшемся дропе
            await notify_admins_report_drop(bot, batch_id)

            # 4. Планируем авто-раздачу неразобранных тем (в 09:50 утра через 2 дня после даты дропа)
            auto_assign_dt = calculate_auto_assign_datetime(batch.get("release_date", ""))
            if auto_assign_dt:
                now_msk = datetime.now(MSK_TZ)
                if auto_assign_dt > now_msk:
                    schedule_auto_assign_job(bot, batch_id, auto_assign_dt)
                else:
                    await auto_assign_report_batch_job(bot, batch_id)

    except Exception as err:
        logger.error("Ошибка при публикации партии докладов %s: %s", batch_id, err, exc_info=True)


def calculate_auto_assign_datetime(release_date_str: str) -> Optional[datetime]:
    """Рассчитать дату и время авто-распределения оставшихся тем.
    
    Правило: если работы не разобраны до следующего дня (до 23:59),
    то оставшиеся работы раздаются рандомно в 9:50 утра следующего дня
    (т.е. через 2 дня после даты дропа).
    """
    from bot.utils.report_helpers import parse_release_date

    release_d = parse_release_date(release_date_str)
    if not release_d:
        return None
    target_date = release_d + timedelta(days=2)
    return datetime(target_date.year, target_date.month, target_date.day, 9, 50, 0, tzinfo=MSK_TZ)


def schedule_auto_assign_job(bot: Bot, batch_id: int, run_datetime: datetime) -> None:
    """Добавить задачу автоматической раздачи неразобранных тем в планировщик."""
    job_id = f"report_auto_assign_{batch_id}"
    scheduler.add_job(
        auto_assign_report_batch_job,
        trigger="date",
        run_date=run_datetime,
        args=[bot, batch_id],
        id=job_id,
        replace_existing=True,
    )
    logger.info(
        "Задача авто-распределения тем #%s запланирована на %s (МСК)",
        batch_id,
        run_datetime.strftime("%Y-%m-%d %H:%M:%S"),
    )


async def auto_assign_report_batch_job(
    bot: Optional[Bot], batch_id: int, db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Исполнение задачи автоматической раздачи неразобранных тем докладов."""
    logger.info("Запуск авто-распределения неразобранных тем для batch_id=%s...", batch_id)
    actual_db = db_path or config.DB_PATH
    result = await auto_assign_remaining_topics(batch_id, actual_db)
    batch = result.get("batch")
    if not batch:
        logger.warning("Партия %s не найдена для авто-распределения.", batch_id)
        return result

    subj_name = batch.get("subject_name", "Предмет")
    seminar_date = batch.get("seminar_date", "—")
    assigned = result.get("assigned", [])
    unassigned_count = result.get("unassigned_count", 0)
    remaining_unassigned = result.get("remaining_unassigned", 0)

    url = config.get_safe_web_app_url()
    app_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎤 Открыть темы в Mini App",
                    web_app=WebAppInfo(url=url),
                )
            ]
        ]
    )

    if bot:
        # 1. Если все темы были разобраны студентами добровольно
        if unassigned_count == 0:
            logger.info("Все темы партии #%s разобраны студентами самостоятельно.", batch_id)
            admin_ids = await get_all_admin_ids(actual_db)
            all_claimed_text = (
                "🎉 <b>Все темы докладов разобраны!</b>\n\n"
                f"По предмету «<b>{html.escape(subj_name)}</b>» (семинар: <code>{html.escape(seminar_date)}</code>) "
                "все темы были успешно заняты студентами до дедлайна.\n"
                "Автоматическое распределение не потребовалось! 👏"
            )
            for adm_id in admin_ids:
                try:
                    await bot.send_message(chat_id=adm_id, text=all_claimed_text, reply_markup=app_markup)
                except Exception as e:
                    logger.debug("Не удалось отправить отчет старосте %s: %s", adm_id, e)
            return result

        # 2. Уведомляем каждого студента, которому назначен доклад
        for item in assigned:
            topic = item["topic"]
            student = item["student"]
            student_text = (
                "🎲 <b>Вам автоматически назначен доклад!</b> 📚\n\n"
                "Поскольку к дедлайну (23:59) оставались свободные темы, "
                "рандомайзер распределил оставшиеся доклады среди студентов.\n\n"
                f"📚 <b>Предмет:</b> «<b>{html.escape(subj_name)}</b>»\n"
                f"🗓 <b>Дата семинара:</b> <code>{html.escape(seminar_date)}</code>\n"
                f"🎯 <b>Ваша тема (#{topic['topic_number']}):</b>\n"
                f"<blockquote>{html.escape(topic['topic_text'])}</blockquote>\n\n"
                "<i>Пожалуйста, подготовьтесь к выступлению на семинаре!</i>"
            )
            try:
                await bot.send_message(chat_id=student["telegram_id"], text=student_text, reply_markup=app_markup)
            except Exception as e:
                logger.warning("Не удалось уведомить студента %s о назначенном докладе: %s", student["telegram_id"], e)

        # 3. Отправляем детальный отчет администраторам (старостам)
        admin_ids = await get_all_admin_ids(actual_db)
        assigned_lines = []
        for item in assigned:
            t = item["topic"]
            s = item["student"]
            name = s.get("full_name") or (f"@{s['username']}" if s.get("username") else f"ID {s['telegram_id']}")
            assigned_lines.append(f"• Тема #{t['topic_number']}: <b>{html.escape(name)}</b>")

        assigned_block = "\n".join(assigned_lines) if assigned_lines else "<i>Никто не назначен</i>"
        report_text = (
            "🎲 <b>ОТЧЕТ ОБ АВТО-РАСПРЕДЕЛЕНИИ ДОКЛАДОВ</b> 📋\n\n"
            f"Рандомайзер завершил раздачу неразобранных тем:\n"
            f"📚 <b>Предмет:</b> «<b>{html.escape(subj_name)}</b>»\n"
            f"🗓 <b>Дата семинара:</b> <code>{html.escape(seminar_date)}</code>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• Было не разобрано: <b>{unassigned_count}</b>\n"
            f"• Автоматически назначено: <b>{len(assigned)}</b>\n"
            f"• Осталось без докладчика: <b>{remaining_unassigned}</b>\n\n"
            f"👥 <b>Назначенные студенты:</b>\n{assigned_block}\n\n"
            "📢 Все назначенные студенты получили персональные уведомления в личные сообщения."
        )
        for adm_id in admin_ids:
            try:
                await bot.send_message(chat_id=adm_id, text=report_text, reply_markup=app_markup)
            except Exception as e:
                logger.warning("Не удалось отправить отчет об авто-раздаче старосте %s: %s", adm_id, e)

    return result


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
    """Отменить запланированные задачи дропа и авто-распределения в планировщике."""
    cancelled = False
    for job_prefix in ("report_batch_", "report_auto_assign_"):
        job_id = f"{job_prefix}{batch_id}"
        try:
            job = scheduler.get_job(job_id)
            if job:
                scheduler.remove_job(job_id)
                logger.info("Задача планировщика %s успешно удалена.", job_id)
                cancelled = True
        except Exception as e:
            logger.warning("Не удалось удалить задачу %s из планировщика: %s", job_id, e)
    return cancelled


async def restore_pending_report_jobs(bot: Bot) -> int:
    """Восстановление отложенных задач дропов при запуске бота.
    
    Гарантирует, что запланированные доклады не потеряются при перезагрузке сервера.
    """
    pending = await get_pending_report_batches(config.DB_PATH)
    restored_count = 0
    now_msk = datetime.now(MSK_TZ)

    # 1. Заранее получаем уже опубликованные партии для авто-распределения
    pending_auto = await get_pending_auto_assign_batches(config.DB_PATH)

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

    # 2. Восстановление задач авто-распределения для ранее опубликованных партий
    for b in pending_auto:
        batch_id = b["id"]
        auto_assign_dt = calculate_auto_assign_datetime(b.get("release_date", ""))
        if auto_assign_dt:
            if auto_assign_dt > now_msk:
                schedule_auto_assign_job(bot, batch_id, auto_assign_dt)
                restored_count += 1
            else:
                logger.info("Время авто-распределения #%s уже прошло, выполняем раздачу...", batch_id)
                await auto_assign_report_batch_job(bot, batch_id)
                restored_count += 1

    logger.info("Восстановлено запланированных задач докладов: %d", restored_count)
    # Очищаем файлы домашних заданий старше 7 дней при старте
    try:
        cleaned_files = await cleanup_expired_homework_files(days=7, db_path=config.DB_PATH)
        if cleaned_files:
            logger.info("При запуске очищено просроченных файлов ДЗ: %d", len(cleaned_files))
    except Exception as e:
        logger.warning("Ошибка при стартовой очистке просроченных файлов ДЗ: %s", e)

    return restored_count


async def cleanup_expired_homework_files_job(db_path: Optional[str] = None) -> int:
    """Периодическая задача: очистка файлов домашних заданий старше 7 дней."""
    target_db = db_path or config.DB_PATH
    try:
        cleaned = await cleanup_expired_homework_files(days=7, db_path=target_db)
        if cleaned:
            logger.info("Фоновая очистка: удалено %d файлов ДЗ с истекшим сроком (7 дней)", len(cleaned))
        return len(cleaned)
    except Exception as e:
        logger.error("Ошибка при фоновой очистке файлов ДЗ: %s", e, exc_info=True)
        return 0


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

    # Задача: каждый час проверять файлы ДЗ старше 7 дней и удалять их с диска
    scheduler.add_job(
        cleanup_expired_homework_files_job,
        trigger="interval",
        hours=1,
        args=[config.DB_PATH],
        id="homework_files_cleanup_7d",
        replace_existing=True,
    )
    logger.info("Фоновая задача автоочистки файлов ДЗ (TTL 7 дней, каждый час) зарегистрирована.")
    return scheduler
