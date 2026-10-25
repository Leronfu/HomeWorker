"""Обработчики управления домашними заданиями в панели старосты."""

import html
import logging
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import config
from bot.database import (
    add_homework,
    delete_homework,
    get_all_subjects,
    get_homework_by_id,
    get_homework_by_subject,
    get_or_create_subject,
    get_subject_by_id,
    update_homework,
)
from bot.handlers.states import HomeworkAdminStates
from bot.keyboards import (
    get_admin_confirm_delete_hw_keyboard,
    get_admin_homework_detail_keyboard,
    get_admin_homework_list_keyboard,
    get_admin_homework_menu_keyboard,
    get_cancel_hw_keyboard,
    get_subjects_keyboard,
)
from bot.utils import format_homework_detail_admin

logger = logging.getLogger("AdminHomeworkHandler")
router = Router(name="admin_homework_router")


def _is_admin_check(telegram_id: int) -> bool:
    """Проверка прав старосты/администратора."""
    return config.is_admin(telegram_id)


# =====================================================================
# Главное меню раздела ДЗ в панели старосты
# =====================================================================

@router.callback_query(F.data == "admin_hw_menu")
async def open_admin_homework_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Главное меню раздела ДЗ."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    text = (
        "📚 <b>Управление домашними заданиями</b>\n\n"
        "Здесь вы можете:\n"
        "• <b>Добавить новое ДЗ</b> — выбрать предмет, указать срок сдачи и ввести текст задания.\n"
        "• <b>Список / Редактировать / Удалить</b> — просмотреть все задания по любому предмету, "
        "изменить дедлайн или текст, а также удалить выполненное ДЗ.\n\n"
        "Выберите необходимое действие:"
    )
    if callback.message:
        try:
            await callback.message.edit_text(text=text, reply_markup=get_admin_homework_menu_keyboard())
        except TelegramBadRequest:
            pass
    await callback.answer()


# =====================================================================
# Добавление нового ДЗ (Выбор предмета -> Дедлайн -> Текст задания)
# =====================================================================

@router.callback_query(F.data == "ahw_menu_add")
async def choose_subject_to_add_homework(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор предмета для добавления ДЗ."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    subjects = await get_all_subjects(config.DB_PATH)
    text = (
        "➕ <b>Добавление домашнего задания</b>\n\n"
        "Выберите предмет, по которому хотите выдать задание группе:"
    )
    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_subjects_keyboard(
                    subjects=subjects,
                    callback_prefix="ahw_start_add",
                    back_callback="admin_hw_menu",
                    extra_buttons=[
                        InlineKeyboardButton(
                            text="✏️ Ввести другой предмет вручную",
                            callback_data="ahw_custom_subject",
                        )
                    ],
                ),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.callback_query(F.data == "ahw_custom_subject")
async def ask_custom_subject_name(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрос ручного ввода названия предмета."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(HomeworkAdminStates.waiting_for_custom_subject)
    text = (
        "✏️ <b>Ввод названия предмета вручную</b>\n\n"
        "Отправьте сообщением название дисциплины (например: <i>Нейропсихология</i>):"
    )
    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_cancel_hw_keyboard(back_callback="ahw_menu_add"),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.message(HomeworkAdminStates.waiting_for_custom_subject, F.text)
async def process_custom_subject_name(message: Message, state: FSMContext) -> None:
    """Обработка введенного названия предмета."""
    if not _is_admin_check(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к панели старосты.")
        await state.clear()
        return

    subject_name = message.text.strip()
    if not subject_name or len(subject_name) < 2:
        await message.answer("⚠️ Название предмета слишком короткое. Введите корректное название:")
        return

    subj = await get_or_create_subject(subject_name, config.DB_PATH)
    await state.set_state(HomeworkAdminStates.waiting_for_due_date)
    await state.update_data(subject_id=subj["id"], subject_name=subj["name"])

    text = (
        f"➕ <b>Добавление задания: {html.escape(subj['name'])}</b>\n\n"
        "Шаг 1 из 2: Отправьте сообщением <b>срок сдачи (дедлайн)</b>.\n"
        "<i>Например: 15.11.2026 или К следующему вторнику</i>"
    )
    await message.answer(
        text=text,
        reply_markup=get_cancel_hw_keyboard(back_callback="ahw_menu_add"),
    )


@router.callback_query(F.data.startswith("ahw_start_add:"))
async def start_add_homework_flow(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало FSM-потока: ввод даты сдачи задания."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    _, subj_id_raw = callback.data.split(":", 1)
    subject_id = int(subj_id_raw)
    subject = await get_subject_by_id(subject_id, config.DB_PATH)

    if not subject:
        await callback.answer("Предмет не найден.", show_alert=True)
        return

    await state.set_state(HomeworkAdminStates.waiting_for_due_date)
    await state.update_data(subject_id=subject_id, subject_name=subject["name"])

    text = (
        f"➕ <b>Добавление задания: {html.escape(subject['name'])}</b>\n\n"
        "Шаг 1 из 2: Отправьте сообщением <b>срок сдачи (дедлайн)</b>.\n"
        "<i>Например: 15.11.2026 или К следующему вторнику</i>"
    )
    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_cancel_hw_keyboard(back_callback="ahw_menu_add"),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.message(HomeworkAdminStates.waiting_for_due_date, F.text)
async def process_due_date_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода даты сдачи задания."""
    if not _is_admin_check(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к панели старосты.")
        await state.clear()
        return

    due_date = message.text.strip()
    if due_date.lower() in ("/cancel", "отмена"):
        await state.clear()
        await message.answer(
            "❌ Добавление задания отменено.",
            reply_markup=get_admin_homework_menu_keyboard(),
        )
        return

    await state.update_data(due_date=due_date)
    await state.set_state(HomeworkAdminStates.waiting_for_task_text)

    data = await state.get_data()
    subject_name = data.get("subject_name", "Предмет")

    await message.answer(
        f"📚 Предмет: <b>{html.escape(subject_name)}</b>\n"
        f"📅 Срок сдачи: <code>{html.escape(due_date)}</code>\n\n"
        "Шаг 2 из 2: Отправьте сообщением <b>текст задания</b>\n"
        "<i>(номера параграфов, вопросы, ссылки или описание того, что нужно сделать):</i>",
        reply_markup=get_cancel_hw_keyboard(back_callback="ahw_menu_add"),
    )


@router.message(HomeworkAdminStates.waiting_for_task_text, F.text)
async def process_task_text_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода текста задания и сохранение в базу данных."""
    if not _is_admin_check(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к панели старосты.")
        await state.clear()
        return

    task_text = message.text.strip()
    if task_text.lower() in ("/cancel", "отмена"):
        await state.clear()
        await message.answer(
            "❌ Добавление задания отменено.",
            reply_markup=get_admin_homework_menu_keyboard(),
        )
        return

    data = await state.get_data()
    subject_id = data.get("subject_id")
    due_date = data.get("due_date", "—")
    subject_name = data.get("subject_name", "Предмет")

    if not subject_id:
        await state.clear()
        await message.answer("⚠️ Ошибка контекста: предмет не выбран.", reply_markup=get_admin_homework_menu_keyboard())
        return

    try:
        hw_id = await add_homework(
            subject_id=subject_id,
            due_date=due_date,
            task_text=task_text,
            db_path=config.DB_PATH,
        )
        await state.clear()

        confirm_text = (
            f"✅ <b>Домашнее задание #{hw_id} успешно опубликовано!</b>\n\n"
            f"📚 <b>Предмет:</b> {html.escape(subject_name)}\n"
            f"📅 <b>Срок:</b> <code>{html.escape(due_date)}</code>\n\n"
            f"📖 <b>Задание:</b>\n{html.escape(task_text)}"
        )

        buttons = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"📋 Список ДЗ ({subject_name[:18]}...)",
                        callback_data=f"ahw_list_subj:{subject_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="➕ Добавить ещё одно ДЗ",
                        callback_data=f"ahw_start_add:{subject_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="« В меню ДЗ",
                        callback_data="admin_hw_menu",
                    )
                ],
            ]
        )

        await message.answer(text=confirm_text, reply_markup=buttons)
    except Exception as e:
        logger.error("Ошибка при сохранении ДЗ в БД: %s", e, exc_info=True)
        await state.clear()
        await message.answer("⚠️ Произошла ошибка при сохранении задания в базу данных.")


# =====================================================================
# Просмотр и управление существующими заданиями
# =====================================================================

@router.callback_query(F.data == "ahw_menu_list")
async def choose_subject_to_view_homework(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор предмета для просмотра и редактирования существующих заданий."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    subjects = await get_all_subjects(config.DB_PATH)
    text = (
        "📋 <b>Список и редактирование домашних заданий</b>\n\n"
        "Выберите предмет, чтобы просмотреть выданные задания или изменить/удалить их:"
    )
    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_subjects_keyboard(
                    subjects=subjects,
                    callback_prefix="ahw_list_subj",
                    back_callback="admin_hw_menu",
                ),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith("ahw_list_subj:"))
async def show_admin_subject_homework_list(callback: CallbackQuery, state: FSMContext) -> None:
    """Отображение списка заданий по предмету для старосты."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    _, subj_id_raw = callback.data.split(":", 1)
    subject_id = int(subj_id_raw)

    subject = await get_subject_by_id(subject_id, config.DB_PATH)
    if not subject:
        await callback.answer("Предмет не найден.", show_alert=True)
        return

    homework_list = await get_homework_by_subject(subject_id, config.DB_PATH)
    subject_name = subject["name"]

    if not homework_list:
        text = (
            f"📋 <b>Управление ДЗ: {html.escape(subject_name)}</b>\n\n"
            "<i>По этому предмету пока нет добавленных заданий.</i>"
        )
    else:
        text = (
            f"📋 <b>Управление ДЗ: {html.escape(subject_name)}</b>\n\n"
            f"Найдено заданий: <b>{len(homework_list)}</b>.\n"
            "Нажмите на задание ниже, чтобы отредактировать его или удалить:"
        )

    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_admin_homework_list_keyboard(homework_list, subject_id),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith("ahw_detail:"))
async def show_admin_homework_detail(callback: CallbackQuery, state: FSMContext) -> None:
    """Карточка конкретного ДЗ со списком действий (изменить текст/срок/удалить)."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    _, hw_id_raw = callback.data.split(":", 1)
    homework_id = int(hw_id_raw)

    hw = await get_homework_by_id(homework_id, config.DB_PATH)
    if not hw:
        await callback.answer("Задание не найдено или уже было удалено.", show_alert=True)
        return

    text = format_homework_detail_admin(hw)
    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_admin_homework_detail_keyboard(homework_id, hw["subject_id"]),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


# =====================================================================
# Редактирование текста задания
# =====================================================================

@router.callback_query(F.data.startswith("ahw_edit_text:"))
async def start_edit_homework_text(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало редактирования текста задания."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    _, hw_id_raw = callback.data.split(":", 1)
    homework_id = int(hw_id_raw)

    hw = await get_homework_by_id(homework_id, config.DB_PATH)
    if not hw:
        await callback.answer("Задание не найдено.", show_alert=True)
        return

    await state.set_state(HomeworkAdminStates.waiting_for_edit_task_text)
    await state.update_data(homework_id=homework_id, subject_id=hw["subject_id"])

    text = (
        f"✏️ <b>Редактирование текста задания #{homework_id}</b>\n\n"
        f"<b>Текущий текст:</b>\n{html.escape(hw['task_text'])}\n\n"
        "Отправьте сообщением <b>новый текст задания</b>:"
    )
    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_cancel_hw_keyboard(back_callback=f"ahw_detail:{homework_id}"),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.message(HomeworkAdminStates.waiting_for_edit_task_text, F.text)
async def process_edit_task_text_input(message: Message, state: FSMContext) -> None:
    """Сохранение нового текста задания."""
    if not _is_admin_check(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        await state.clear()
        return

    new_text = message.text.strip()
    data = await state.get_data()
    homework_id = data.get("homework_id")
    subject_id = data.get("subject_id")

    if new_text.lower() in ("/cancel", "отмена"):
        await state.clear()
        await message.answer("❌ Изменение текста отменено.")
        if homework_id:
            hw = await get_homework_by_id(homework_id, config.DB_PATH)
            if hw:
                await message.answer(
                    format_homework_detail_admin(hw),
                    reply_markup=get_admin_homework_detail_keyboard(homework_id, hw["subject_id"]),
                )
        return

    if not homework_id:
        await state.clear()
        await message.answer("⚠️ Ошибка: задание не найдено.", reply_markup=get_admin_homework_menu_keyboard())
        return

    await update_homework(homework_id=homework_id, task_text=new_text, db_path=config.DB_PATH)
    await state.clear()

    hw_updated = await get_homework_by_id(homework_id, config.DB_PATH)
    confirm_text = f"✅ <b>Текст задания #{homework_id} успешно обновлен!</b>\n\n"
    if hw_updated:
        confirm_text += format_homework_detail_admin(hw_updated)

    markup = get_admin_homework_detail_keyboard(homework_id, subject_id or 1)
    await message.answer(text=confirm_text, reply_markup=markup)


# =====================================================================
# Редактирование дедлайна (срока сдачи)
# =====================================================================

@router.callback_query(F.data.startswith("ahw_edit_date:"))
async def start_edit_homework_date(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало редактирования даты сдачи задания."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    _, hw_id_raw = callback.data.split(":", 1)
    homework_id = int(hw_id_raw)

    hw = await get_homework_by_id(homework_id, config.DB_PATH)
    if not hw:
        await callback.answer("Задание не найдено.", show_alert=True)
        return

    await state.set_state(HomeworkAdminStates.waiting_for_edit_due_date)
    await state.update_data(homework_id=homework_id, subject_id=hw["subject_id"])

    text = (
        f"📅 <b>Изменение срока сдачи задания #{homework_id}</b>\n\n"
        f"<b>Текущий срок:</b> <code>{html.escape(hw['due_date'])}</code>\n\n"
        "Отправьте сообщением <b>новый срок сдачи</b> (например, <i>20.11.2026</i>):"
    )
    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_cancel_hw_keyboard(back_callback=f"ahw_detail:{homework_id}"),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.message(HomeworkAdminStates.waiting_for_edit_due_date, F.text)
async def process_edit_due_date_input(message: Message, state: FSMContext) -> None:
    """Сохранение нового срока сдачи задания."""
    if not _is_admin_check(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        await state.clear()
        return

    new_date = message.text.strip()
    data = await state.get_data()
    homework_id = data.get("homework_id")
    subject_id = data.get("subject_id")

    if new_date.lower() in ("/cancel", "отмена"):
        await state.clear()
        await message.answer("❌ Изменение срока сдачи отменено.")
        if homework_id:
            hw = await get_homework_by_id(homework_id, config.DB_PATH)
            if hw:
                await message.answer(
                    format_homework_detail_admin(hw),
                    reply_markup=get_admin_homework_detail_keyboard(homework_id, hw["subject_id"]),
                )
        return

    if not homework_id:
        await state.clear()
        await message.answer("⚠️ Ошибка: задание не найдено.", reply_markup=get_admin_homework_menu_keyboard())
        return

    await update_homework(homework_id=homework_id, due_date=new_date, db_path=config.DB_PATH)
    await state.clear()

    hw_updated = await get_homework_by_id(homework_id, config.DB_PATH)
    confirm_text = f"✅ <b>Срок сдачи задания #{homework_id} успешно обновлен!</b>\n\n"
    if hw_updated:
        confirm_text += format_homework_detail_admin(hw_updated)

    markup = get_admin_homework_detail_keyboard(homework_id, subject_id or 1)
    await message.answer(text=confirm_text, reply_markup=markup)


# =====================================================================
# Удаление домашнего задания
# =====================================================================

@router.callback_query(F.data.startswith("ahw_del_confirm:"))
async def confirm_delete_homework(callback: CallbackQuery) -> None:
    """Запрос подтверждения удаления домашнего задания."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    _, hw_id_raw = callback.data.split(":", 1)
    homework_id = int(hw_id_raw)

    hw = await get_homework_by_id(homework_id, config.DB_PATH)
    if not hw:
        await callback.answer("Задание уже удалено.", show_alert=True)
        return

    text = (
        f"🗑 <b>Удаление домашнего задания #{homework_id}</b>\n\n"
        f"Предмет: <b>{html.escape(hw['subject_name'])}</b>\n"
        f"Дедлайн: <code>{html.escape(hw['due_date'])}</code>\n\n"
        "Вы действительно хотите удалить это задание? Действие необратимо."
    )
    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_admin_confirm_delete_hw_keyboard(homework_id, hw["subject_id"]),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith("ahw_del_do:"))
async def execute_delete_homework(callback: CallbackQuery) -> None:
    """Выполнение удаления задания из базы данных."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    homework_id = int(parts[1])
    subject_id = int(parts[2])

    deleted = await delete_homework(homework_id, config.DB_PATH)
    if deleted:
        await callback.answer("Задание успешно удалено! 🗑", show_alert=True)
    else:
        await callback.answer("Задание не найдено или уже было удалено.", show_alert=True)

    # Возвращаемся к обновленному списку заданий по предмету
    subject = await get_subject_by_id(subject_id, config.DB_PATH)
    homework_list = await get_homework_by_subject(subject_id, config.DB_PATH)
    subject_name = subject["name"] if subject else "Предмет"

    if not homework_list:
        text = (
            f"📋 <b>Управление ДЗ: {html.escape(subject_name)}</b>\n\n"
            "<i>Все задания по этому предмету удалены (список пуст).</i>"
        )
    else:
        text = (
            f"📋 <b>Управление ДЗ: {html.escape(subject_name)}</b>\n\n"
            f"Осталось заданий: <b>{len(homework_list)}</b>.\n"
            "Выберите задание для управления:"
        )

    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_admin_homework_list_keyboard(homework_list, subject_id),
            )
        except TelegramBadRequest:
            pass
