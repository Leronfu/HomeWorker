"""Обработчики раздела «Домашнее задание» для студентов."""

import logging
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from bot import config
from bot.database import get_all_subjects, get_homework_by_subject, get_subject_by_id
from bot.keyboards import get_student_homework_keyboard, get_subjects_keyboard
from bot.utils import format_homework_list_student

logger = logging.getLogger("HomeworkHandler")
router = Router(name="homework_router")


@router.message(F.text == "📚 Домашнее задание")
async def show_homework_subjects_menu(message: Message) -> None:
    """Вывод списка 10 предметов при нажатии кнопки «📚 Домашнее задание» в Главном меню."""
    try:
        subjects = await get_all_subjects(config.DB_PATH)
        await message.answer(
            "📚 <b>Домашние задания учебной группы</b>\n\n"
            "Выберите предмет из списка ниже, чтобы посмотреть актуальные задания и дедлайны:",
            reply_markup=get_subjects_keyboard(subjects, callback_prefix="hw_subj"),
        )
    except Exception as e:
        logger.error("Ошибка при получении списка предметов: %s", e, exc_info=True)
        await message.answer("⚠️ Не удалось загрузить список предметов. Попробуйте позже.")


@router.callback_query(F.data == "hw_list_subjects")
async def back_to_homework_subjects(callback: CallbackQuery) -> None:
    """Возврат к списку предметов из карточки конкретной дисциплины."""
    try:
        subjects = await get_all_subjects(config.DB_PATH)
        if callback.message:
            await callback.message.edit_text(
                "📚 <b>Домашние задания учебной группы</b>\n\n"
                "Выберите предмет из списка ниже, чтобы посмотреть актуальные задания и дедлайны:",
                reply_markup=get_subjects_keyboard(subjects, callback_prefix="hw_subj"),
            )
        await callback.answer()
    except TelegramBadRequest:
        await callback.answer()
    except Exception as e:
        logger.error("Ошибка при возврате к списку предметов: %s", e, exc_info=True)
        await callback.answer("⚠️ Произошла ошибка при загрузке.", show_alert=True)


@router.callback_query(F.data.startswith("hw_subj:"))
async def show_subject_homework(callback: CallbackQuery) -> None:
    """Отображение всех домашних заданий по выбранному предмету."""
    try:
        _, subj_id_raw = callback.data.split(":", 1)
        subject_id = int(subj_id_raw)

        subject = await get_subject_by_id(subject_id, config.DB_PATH)
        if not subject:
            await callback.answer("Предмет не найден в базе данных.", show_alert=True)
            return

        homework_list = await get_homework_by_subject(subject_id, config.DB_PATH)
        text = format_homework_list_student(subject["name"], homework_list)

        if callback.message:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_student_homework_keyboard(subject_id),
            )
        await callback.answer()
    except TelegramBadRequest:
        await callback.answer()
    except Exception as e:
        logger.error("Ошибка при отображении ДЗ по предмету: %s", e, exc_info=True)
        await callback.answer("⚠️ Не удалось загрузить задания.", show_alert=True)


@router.callback_query(F.data.startswith("hw_refresh:"))
async def refresh_subject_homework(callback: CallbackQuery) -> None:
    """Обновление списка ДЗ по текущему предмету."""
    try:
        _, subj_id_raw = callback.data.split(":", 1)
        subject_id = int(subj_id_raw)

        subject = await get_subject_by_id(subject_id, config.DB_PATH)
        if not subject:
            await callback.answer("Предмет не найден.", show_alert=True)
            return

        homework_list = await get_homework_by_subject(subject_id, config.DB_PATH)
        text = format_homework_list_student(subject["name"], homework_list)

        if callback.message:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_student_homework_keyboard(subject_id),
            )
        await callback.answer("🔄 Список заданий обновлен!")
    except TelegramBadRequest:
        await callback.answer("Данные актуальны 👍")
    except Exception as e:
        logger.error("Ошибка при обновлении ДЗ: %s", e, exc_info=True)
        await callback.answer("⚠️ Не удалось обновить задания.", show_alert=True)
