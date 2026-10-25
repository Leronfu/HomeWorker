"""Обработчики Панели старосты и управления расписанием."""

import html
import logging
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import config
from bot.database import (
    clear_week_schedule,
    copy_next_to_current_week,
    get_schedule,
    get_schedule_day,
    update_schedule_day,
)
from bot.handlers.states import ScheduleAdminStates
from bot.keyboards import (
    get_admin_confirm_clear_week_keyboard,
    get_admin_confirm_rollover_keyboard,
    get_admin_edit_day_keyboard,
    get_admin_main_keyboard,
    get_admin_schedule_days_keyboard,
    get_admin_schedule_menu_keyboard,
)
from bot.utils import (
    format_day_preview,
    format_schedule_text,
    get_weekday_name,
)

logger = logging.getLogger("AdminScheduleHandler")
router = Router(name="admin_schedule_router")


def _is_admin_check(telegram_id: int) -> bool:
    """Вспомогательная проверка прав администратора."""
    return config.is_admin(telegram_id)


# =====================================================================
# Главный вход в панель старосты
# =====================================================================

@router.message(F.text == "⚙️ Панель старосты")
async def open_admin_panel(message: Message, state: FSMContext) -> None:
    """Открытие панели старосты из Главного меню."""
    if not _is_admin_check(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к панели старосты.")
        return

    await state.clear()
    await message.answer(
        "⚙️ <b>Панель управления старосты</b>\n\n"
        "Здесь вы можете настраивать расписание занятий, публиковать домашние задания "
        "и управлять дропами тем для докладов.\n\n"
        "Выберите раздел для работы:",
        reply_markup=get_admin_main_keyboard(),
    )


@router.callback_query(F.data == "admin_main_back")
async def back_to_admin_main(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат в главное меню панели старосты."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    if callback.message:
        await callback.message.edit_text(
            "⚙️ <b>Панель управления старосты</b>\n\n"
            "Выберите раздел для работы:",
            reply_markup=get_admin_main_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin_close")
async def close_admin_panel(callback: CallbackQuery, state: FSMContext) -> None:
    """Закрытие панели старосты."""
    await state.clear()
    if callback.message:
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            await callback.message.edit_text("<i>Панель старосты закрыта.</i>")
    await callback.answer()


# =====================================================================
# Меню управления расписанием
# =====================================================================

@router.callback_query(F.data == "admin_sched_menu")
async def open_admin_schedule_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Меню управления расписанием: выбор недели или перенос."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    text = (
        "📅 <b>Управление расписанием занятий</b>\n\n"
        "• <b>Текущая неделя:</b> расписание, которое студенты видят прямо сейчас.\n"
        "• <b>Следующая неделя:</b> расписание на предстоящую неделю (можно заполнять заранее).\n"
        "• <b>Перенос расписания:</b> каждую субботу в 15:00 планировщик переносит следующую неделю в текущую автоматически. "
        "Также вы можете выполнить перенос вручную кнопкой ниже."
    )
    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_admin_schedule_menu_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sched_week:"))
async def open_admin_week_days(callback: CallbackQuery, state: FSMContext) -> None:
    """Отображение списка дней недели выбранного слота (current / next)."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    _, week_type = callback.data.split(":", 1)
    week_title = "Текущая неделя" if week_type == "current" else "Следующая неделя"

    text = (
        f"📅 <b>Редактирование: {week_title}</b>\n\n"
        "Выберите день недели (Пн–Сб) для ввода или изменения расписания:"
    )
    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_admin_schedule_days_keyboard(week_type),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sched_preview:"))
async def preview_week_schedule(callback: CallbackQuery) -> None:
    """Предпросмотр всей недели из админки."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    _, week_type = callback.data.split(":", 1)
    schedule_rows = await get_schedule(week_type, config.DB_PATH)
    text = format_schedule_text(schedule_rows, week_type=week_type)

    back_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="« Назад к дням недели",
                    callback_data=f"admin_sched_week:{week_type}",
                )
            ]
        ]
    )
    if callback.message:
        await callback.message.edit_text(text=text, reply_markup=back_markup)
    await callback.answer()


# =====================================================================
# Редактирование конкретного дня недели
# =====================================================================

@router.callback_query(F.data.startswith("admin_sched_edit_day:"))
async def start_edit_day(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало процесса редактирования расписания на день."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    week_type = parts[1]
    day_of_week = int(parts[2])

    day_record = await get_schedule_day(week_type, day_of_week, config.DB_PATH)
    current_content = day_record["content"] if day_record else ""

    await state.set_state(ScheduleAdminStates.waiting_for_day_content)
    await state.update_data(
        week_type=week_type,
        day_of_week=day_of_week,
        last_msg_id=callback.message.message_id if callback.message else None,
    )

    day_name = get_weekday_name(day_of_week)
    week_title = "Текущая неделя" if week_type == "current" else "Следующая неделя"
    preview = format_day_preview(day_of_week, week_type, current_content)

    instructions = (
        f"{preview}\n\n"
        f"✍️ <b>Отправьте сообщением новый текст расписания для {day_name} ({week_title}).</b>\n\n"
        "<i>Подсказка: пишите каждую пару с новой строки (время, предмет, аудитория).\n"
        "Чтобы очистить расписание на этот день, отправьте «-» или нажмите кнопку «Очистить день» ниже.</i>"
    )

    if callback.message:
        await callback.message.edit_text(
            text=instructions,
            reply_markup=get_admin_edit_day_keyboard(week_type, day_of_week),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sched_clear_day:"))
async def clear_single_day(callback: CallbackQuery, state: FSMContext) -> None:
    """Очистка расписания на выбранный день по нажатию Inline-кнопки."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    week_type = parts[1]
    day_of_week = int(parts[2])

    await update_schedule_day(week_type, day_of_week, "", config.DB_PATH)
    await state.clear()
    await callback.answer("Расписание на этот день очищено! 🗑")

    week_title = "Текущая неделя" if week_type == "current" else "Следующая неделя"
    if callback.message:
        await callback.message.edit_text(
            f"✅ Расписание на {get_weekday_name(day_of_week)} ({week_title}) очищено.\n\n"
            "Выберите следующий день для редактирования:",
            reply_markup=get_admin_schedule_days_keyboard(week_type),
        )


@router.callback_query(F.data.startswith("admin_sched_cancel_edit:"))
async def cancel_edit_day(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена редактирования дня и возврат к выбору дней."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    _, week_type = callback.data.split(":", 1)
    await state.clear()

    if callback.message:
        week_title = "Текущая неделя" if week_type == "current" else "Следующая неделя"
        await callback.message.edit_text(
            f"❌ Редактирование отменено.\n\n"
            f"📅 <b>{week_title}:</b> выберите день недели:",
            reply_markup=get_admin_schedule_days_keyboard(week_type),
        )
    await callback.answer()


@router.message(ScheduleAdminStates.waiting_for_day_content, F.text)
async def process_day_content_input(message: Message, state: FSMContext) -> None:
    """Обработка текстового сообщения с новым расписанием на день."""
    if not _is_admin_check(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к панели старосты.")
        await state.clear()
        return

    input_text = message.text.strip()
    data = await state.get_data()
    week_type = data.get("week_type", "current")
    day_of_week = data.get("day_of_week", 1)

    # Проверка на отмену
    if input_text.lower() in ("/cancel", "отмена"):
        await state.clear()
        week_title = "Текущая неделя" if week_type == "current" else "Следующая неделя"
        await message.answer(
            f"❌ Редактирование отменено.\n\n"
            f"📅 <b>{week_title}:</b> выберите день недели:",
            reply_markup=get_admin_schedule_days_keyboard(week_type),
        )
        return

    # Очистка дня по символу дефиса или слова "нет"
    if input_text in ("-", "—", "нет", "пусто"):
        new_content = ""
    else:
        new_content = input_text

    await update_schedule_day(week_type, day_of_week, new_content, config.DB_PATH)
    await state.clear()

    day_name = get_weekday_name(day_of_week)
    week_title = "Текущая неделя" if week_type == "current" else "Следующая неделя"

    status_desc = "очищено" if not new_content else "сохранено"
    confirm_text = (
        f"✅ <b>Расписание на {day_name} ({week_title}) успешно {status_desc}!</b>\n\n"
        f"<b>Текущий текст:</b>\n"
        f"{html.escape(new_content) if new_content else '<i>(занятий нет / пусто)</i>'}"
    )

    action_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"« К дням ({week_title})",
                    callback_data=f"admin_sched_week:{week_type}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 В меню расписания",
                    callback_data="admin_sched_menu",
                )
            ],
        ]
    )

    await message.answer(text=confirm_text, reply_markup=action_markup)


# =====================================================================
# Очистка всей недели
# =====================================================================

@router.callback_query(F.data.startswith("admin_sched_clear_week_confirm:"))
async def confirm_clear_week(callback: CallbackQuery) -> None:
    """Запрос подтверждения очистки всей недели."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    _, week_type = callback.data.split(":", 1)
    week_title = "Текущей недели" if week_type == "current" else "Следующей недели"

    text = (
        f"⚠️ <b>Внимание! Очистка {week_title}</b>\n\n"
        "Вы действительно хотите удалить расписание на все 6 дней этой недели? "
        "Это действие необратимо."
    )
    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_admin_confirm_clear_week_keyboard(week_type),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sched_clear_week_do:"))
async def execute_clear_week(callback: CallbackQuery) -> None:
    """Выполнение очистки всех дней выбранной недели."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    _, week_type = callback.data.split(":", 1)
    await clear_week_schedule(week_type, config.DB_PATH)
    await callback.answer("Расписание недели полностью очищено! 🗑", show_alert=True)

    week_title = "Текущая неделя" if week_type == "current" else "Следующая неделя"
    if callback.message:
        await callback.message.edit_text(
            f"✅ Расписание на неделю (<b>{week_title}</b>) очищено.\n\n"
            "Выберите день для нового заполнения:",
            reply_markup=get_admin_schedule_days_keyboard(week_type),
        )


# =====================================================================
# Ручной перенос расписания
# =====================================================================

@router.callback_query(F.data == "admin_sched_rollover_confirm")
async def confirm_rollover(callback: CallbackQuery) -> None:
    """Запрос подтверждения ручного переноса следующей недели в текущую."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    text = (
        "⚡ <b>Перенос расписания (Следующая неделя ➔ Текущая неделя)</b>\n\n"
        "⚠️ Расписание из слота «Следующая неделя» заменит текущую неделю.\n"
        "Слот «Следующая неделя» после этого станет пустым.\n\n"
        "Вы уверены, что хотите выполнить перенос прямо сейчас?"
    )
    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_admin_confirm_rollover_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin_sched_rollover_do")
async def execute_rollover(callback: CallbackQuery) -> None:
    """Выполнение ручного переноса недели."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    try:
        await copy_next_to_current_week(config.DB_PATH)
        await callback.answer("✅ Расписание успешно перенесено!", show_alert=True)

        if callback.message:
            await callback.message.edit_text(
                "✅ <b>Перенос успешно выполнен!</b>\n\n"
                "Расписание следующей недели теперь стало текущим, а слот следующей недели очищен.\n\n"
                "Что делаем дальше?",
                reply_markup=get_admin_schedule_menu_keyboard(),
            )
    except Exception as e:
        logger.error("Ошибка при ручном переносе расписания: %s", e, exc_info=True)
        await callback.answer("⚠️ Произошла ошибка при переносе.", show_alert=True)
