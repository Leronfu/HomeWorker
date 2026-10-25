"""Обработчики раздела «Расписание» для студентов."""

import logging
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from bot import config
from bot.database import get_schedule
from bot.keyboards import get_schedule_view_keyboard
from bot.utils import format_schedule_text

logger = logging.getLogger("ScheduleHandler")
router = Router(name="schedule_router")


@router.message(F.text == "📅 Расписание")
async def show_schedule_current_week(message: Message) -> None:
    """Отображение расписания на текущую неделю при нажатии на кнопку в Главном меню."""
    try:
        schedule_rows = await get_schedule("current", config.DB_PATH)
        text = format_schedule_text(schedule_rows, week_type="current")
        await message.answer(
            text=text,
            reply_markup=get_schedule_view_keyboard("current"),
        )
    except Exception as e:
        logger.error("Ошибка при получении расписания: %s", e, exc_info=True)
        await message.answer("⚠️ Не удалось загрузить расписание. Попробуйте чуть позже.")


@router.callback_query(F.data.startswith("sched_view:"))
async def toggle_schedule_week(callback: CallbackQuery) -> None:
    """Переключение между текущей и следующей неделей через Inline-кнопку."""
    _, week_type = callback.data.split(":", 1)
    if week_type not in ("current", "next"):
        await callback.answer("Некорректная неделя", show_alert=True)
        return

    try:
        schedule_rows = await get_schedule(week_type, config.DB_PATH)
        text = format_schedule_text(schedule_rows, week_type=week_type)
        if callback.message:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_schedule_view_keyboard(week_type),
            )
        await callback.answer()
    except TelegramBadRequest:
        # Текст не изменился
        await callback.answer()
    except Exception as e:
        logger.error("Ошибка при переключении недели расписания: %s", e, exc_info=True)
        await callback.answer("⚠️ Ошибка обновления расписания.", show_alert=True)


@router.callback_query(F.data.startswith("sched_refresh:"))
async def refresh_schedule_view(callback: CallbackQuery) -> None:
    """Обновление текущего экрана расписания."""
    _, week_type = callback.data.split(":", 1)
    if week_type not in ("current", "next"):
        week_type = "current"

    try:
        schedule_rows = await get_schedule(week_type, config.DB_PATH)
        text = format_schedule_text(schedule_rows, week_type=week_type)
        if callback.message:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_schedule_view_keyboard(week_type),
            )
        await callback.answer("🔄 Расписание обновлено!")
    except TelegramBadRequest:
        await callback.answer("Данные актуальны 👍")
    except Exception as e:
        logger.error("Ошибка при обновлении расписания: %s", e, exc_info=True)
        await callback.answer("⚠️ Ошибка обновления.", show_alert=True)
