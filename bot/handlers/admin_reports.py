"""Обработчики управления докладами в панели старосты (Шаг 6)."""

import html
import logging
from datetime import datetime
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import config
from bot.database import (
    create_report_batch,
    delete_report_batch,
    get_all_report_batches,
    get_all_subjects,
    get_batch_by_id,
    get_batch_topics,
    get_subject_by_id,
)
from bot.handlers.states import ReportAdminStates
from bot.keyboards import (
    get_admin_batch_detail_keyboard,
    get_admin_batches_list_keyboard,
    get_admin_confirm_delete_batch_keyboard,
    get_admin_reports_menu_keyboard,
    get_cancel_reports_keyboard,
    get_subjects_keyboard,
)
from bot.utils import (
    cancel_scheduled_report_job,
    format_report_batch_admin,
    generate_random_release_datetime,
    parse_release_date,
    parse_topics_text,
    publish_report_job,
    schedule_report_release,
)
from bot.utils.report_helpers import MSK_TZ

logger = logging.getLogger("AdminReportsHandler")
router = Router(name="admin_reports_router")


def _is_admin_check(telegram_id: int) -> bool:
    """Проверка прав старосты/администратора."""
    return config.is_admin(telegram_id)


# =====================================================================
# Главное меню раздела докладов
# =====================================================================

@router.callback_query(F.data == "admin_reports_menu")
async def open_admin_reports_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Главное меню управления докладами в панели старосты."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    text = (
        "🎤 <b>Управление докладами и «Честный дроп»</b>\n\n"
        "Здесь вы можете:\n"
        "• <b>Запланировать новый дроп</b> — выбрать предмет, дату семинара, ввести темы "
        "и указать день публикации. Бот сам выберет случайное время (10:00–21:00) и выложит темы без предупреждения!\n"
        "• <b>Список партий</b> — просмотреть все запланированные и опубликованные доклады, "
        "узнать время дропа, принудительно опубликовать темы раньше срока или удалить партию.\n\n"
        "Выберите необходимое действие:"
    )
    if callback.message:
        try:
            await callback.message.edit_text(text=text, reply_markup=get_admin_reports_menu_keyboard())
        except TelegramBadRequest:
            pass
    await callback.answer()


# =====================================================================
# FSM: Создание новой партии докладов
# =====================================================================

@router.callback_query(F.data == "arep_menu_add")
async def choose_subject_for_reports(callback: CallbackQuery, state: FSMContext) -> None:
    """Шаг 1: Выбор дисциплины из 10 доступных."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    subjects = await get_all_subjects(config.DB_PATH)
    text = (
        "➕ <b>Создание новой партии докладов</b>\n\n"
        "Выберите предмет, по которому будут подготовлены доклады:"
    )
    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_subjects_keyboard(
                    subjects=subjects,
                    callback_prefix="arep_pick_subj",
                    back_callback="admin_reports_menu",
                ),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith("arep_pick_subj:"))
async def start_report_fsm_seminar_date(callback: CallbackQuery, state: FSMContext) -> None:
    """Шаг 2: Ввод даты проведения семинара."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    _, subj_id_raw = callback.data.split(":", 1)
    subject_id = int(subj_id_raw)
    subject = await get_subject_by_id(subject_id, config.DB_PATH)

    if not subject:
        await callback.answer("Предмет не найден.", show_alert=True)
        return

    await state.set_state(ReportAdminStates.waiting_for_seminar_date)
    await state.update_data(subject_id=subject_id, subject_name=subject["name"])

    text = (
        f"🎤 <b>Предмет: {html.escape(subject['name'])}</b>\n\n"
        "Шаг 1 из 3: Отправьте сообщением <b>дату семинара</b>, к которой готовятся доклады.\n"
        "<i>Например: 15 ноября или 15.11.2026</i>"
    )
    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_cancel_reports_keyboard("arep_menu_add"),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.message(ReportAdminStates.waiting_for_seminar_date, F.text)
async def process_seminar_date_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода даты семинара."""
    if not _is_admin_check(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        await state.clear()
        return

    seminar_date = message.text.strip()
    if seminar_date.lower() in ("/cancel", "отмена"):
        await state.clear()
        await message.answer("❌ Создание докладов отменено.", reply_markup=get_admin_reports_menu_keyboard())
        return

    await state.update_data(seminar_date=seminar_date)
    await state.set_state(ReportAdminStates.waiting_for_topics_list)

    text = (
        f"🗓 Дата семинара: <b>{html.escape(seminar_date)}</b>\n\n"
        "Шаг 2 из 3: Отправьте <b>список тем / вопросов одним сообщением</b>.\n\n"
        "📌 <i>Правило: пишите каждую тему с новой строки.\n"
        "Номера ставить не обязательно — бот автоматически очистит лишние дефисы/цифры и пронумерует темы аккуратно (1, 2, 3...).</i>"
    )
    await message.answer(text=text, reply_markup=get_cancel_reports_keyboard("arep_menu_add"))


@router.message(ReportAdminStates.waiting_for_topics_list, F.text)
async def process_topics_list_input(message: Message, state: FSMContext) -> None:
    """Обработка и парсинг списка тем докладов."""
    if not _is_admin_check(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        await state.clear()
        return

    raw_text = message.text.strip()
    if raw_text.lower() in ("/cancel", "отмена"):
        await state.clear()
        await message.answer("❌ Создание докладов отменено.", reply_markup=get_admin_reports_menu_keyboard())
        return

    topics = parse_topics_text(raw_text)
    if not topics:
        await message.answer(
            "⚠️ Не удалось распознать ни одной темы. Пожалуйста, отправьте список тем (каждая с новой строки):",
            reply_markup=get_cancel_reports_keyboard("arep_menu_add"),
        )
        return

    await state.update_data(topics=topics)
    await state.set_state(ReportAdminStates.waiting_for_release_date)

    topics_preview = "\n".join([f"{i}. {html.escape(t)}" for i, t in enumerate(topics[:5], 1)])
    more_note = f"\n<i>...и ещё {len(topics) - 5} тем</i>" if len(topics) > 5 else ""

    text = (
        f"✅ <b>Успешно распознано тем: {len(topics)}</b>\n\n"
        f"<b>Пример тем:</b>\n{topics_preview}{more_note}\n\n"
        "Шаг 3 из 3: Введите <b>дату дропа</b> (день, когда бот выложит темы в группу).\n"
        "Формат: <code>ДД.ММ.ГГГГ</code> (например: <code>28.10.2026</code> или <code>28.10</code>).\n\n"
        "🎲 <i>Бот сам выберет случайное время в течение этого дня (с 10:00 до 21:00) "
        "и опубликует доклады неожиданно для равных шансов!</i>"
    )
    await message.answer(text=text, reply_markup=get_cancel_reports_keyboard("arep_menu_add"))


@router.message(ReportAdminStates.waiting_for_release_date, F.text)
async def process_release_date_input(message: Message, state: FSMContext) -> None:
    """Обработка даты дропа, расчет случайного времени и постановка в APScheduler."""
    if not _is_admin_check(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        await state.clear()
        return

    raw_date = message.text.strip()
    if raw_date.lower() in ("/cancel", "отмена"):
        await state.clear()
        await message.answer("❌ Создание докладов отменено.", reply_markup=get_admin_reports_menu_keyboard())
        return

    release_date = parse_release_date(raw_date)
    if not release_date:
        await message.answer(
            "⚠️ Не удалось распознать дату. Пожалуйста, введите дату в формате <code>ДД.ММ.ГГГГ</code> (например, <code>28.10.2026</code>):",
            reply_markup=get_cancel_reports_keyboard("arep_menu_add"),
        )
        return

    now_msk = datetime.now(MSK_TZ)
    if release_date < now_msk.date():
        await message.answer(
            "⚠️ Дата дропа не может быть в прошлом! Введите сегодняшнюю или будущую дату (например, <code>29.10.2026</code>):",
            reply_markup=get_cancel_reports_keyboard("arep_menu_add"),
        )
        return

    # Генерация случайного времени в дневном интервале 10:00 - 20:59 МСК
    random_dt = generate_random_release_datetime(release_date)
    random_dt_str = random_dt.strftime("%Y-%m-%d %H:%M:%S")
    release_date_str = release_date.strftime("%d.%m.%Y")

    data = await state.get_data()
    subject_id = data["subject_id"]
    subject_name = data["subject_name"]
    seminar_date = data["seminar_date"]
    topics = data["topics"]

    try:
        batch_id = await create_report_batch(
            subject_id=subject_id,
            seminar_date=seminar_date,
            release_date=release_date_str,
            release_datetime_random=random_dt_str,
            topics=topics,
            db_path=config.DB_PATH,
        )

        # Ставим задачу в планировщик APScheduler
        if message.bot:
            schedule_report_release(message.bot, batch_id, random_dt)

        await state.clear()

        confirm_text = (
            f"🎉 <b>Дроп докладов #{batch_id} успешно запланирован!</b>\n\n"
            f"📚 <b>Предмет:</b> {html.escape(subject_name)}\n"
            f"🗓 <b>Семинар:</b> <code>{html.escape(seminar_date)}</code>\n"
            f"📅 <b>Дата дропа:</b> <code>{release_date_str}</code>\n"
            f"⏰ <b>Случайное время дропа:</b> <code>{random_dt.strftime('%H:%M:%S')} (МСК)</code>\n"
            f"<i>(Точное время известно только старосте, студенты увидят темы только в момент дропа!)</i>\n\n"
            f"📝 <b>Всего тем:</b> {len(topics)}"
        )

        buttons = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👁 Посмотреть карточку партии",
                        callback_data=f"arep_detail:{batch_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📋 Все партии докладов",
                        callback_data="arep_menu_list",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="« В меню докладов",
                        callback_data="admin_reports_menu",
                    )
                ],
            ]
        )

        await message.answer(text=confirm_text, reply_markup=buttons)

    except Exception as e:
        logger.error("Ошибка при создании партии докладов: %s", e, exc_info=True)
        await state.clear()
        await message.answer("⚠️ Произошла ошибка при сохранении партии докладов в базу данных.")


# =====================================================================
# Список партий и карточка управления
# =====================================================================

@router.callback_query(F.data == "arep_menu_list")
async def show_admin_batches_list(callback: CallbackQuery, state: FSMContext) -> None:
    """Отображение списка всех партий докладов."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    batches = await get_all_report_batches(config.DB_PATH)

    if not batches:
        text = (
            "📋 <b>Список партий докладов</b>\n\n"
            "<i>Запланированных или опубликованных партий докладов пока нет.</i>"
        )
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Запланировать новый дроп",
                        callback_data="arep_menu_add",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="« В меню докладов",
                        callback_data="admin_reports_menu",
                    )
                ],
            ]
        )
    else:
        text = (
            "📋 <b>Список партий докладов</b>\n\n"
            "• ⏳ — ожидает наступления времени дропа (недоступно группе)\n"
            "• 📢 — опубликовано (темы видны группе)\n\n"
            "Нажмите на партию ниже для просмотра тем или управления:"
        )
        markup = get_admin_batches_list_keyboard(batches)

    if callback.message:
        try:
            await callback.message.edit_text(text=text, reply_markup=markup)
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith("arep_detail:"))
async def show_admin_batch_detail(callback: CallbackQuery, state: FSMContext) -> None:
    """Детальный просмотр партии докладов и тем."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    _, batch_id_raw = callback.data.split(":", 1)
    batch_id = int(batch_id_raw)

    batch = await get_batch_by_id(batch_id, config.DB_PATH)
    if not batch:
        await callback.answer("Партия докладов не найдена.", show_alert=True)
        return

    topics = await get_batch_topics(batch_id, config.DB_PATH)
    text = format_report_batch_admin(batch, topics)

    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_admin_batch_detail_keyboard(batch),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith("arep_pub_now:"))
async def publish_batch_immediately(callback: CallbackQuery) -> None:
    """Принудительная публикация дропа прямо сейчас по кнопке старосты."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    _, batch_id_raw = callback.data.split(":", 1)
    batch_id = int(batch_id_raw)

    # Отменяем задачу в планировщике, если она была запланирована на потом
    cancel_scheduled_report_job(batch_id)

    # Выполняем публикацию
    if callback.bot:
        await publish_report_job(callback.bot, batch_id)

    await callback.answer("⚡ Дроп опубликован прямо сейчас! Темы открыты.", show_alert=True)

    # Обновляем карточку
    batch = await get_batch_by_id(batch_id, config.DB_PATH)
    topics = await get_batch_topics(batch_id, config.DB_PATH)
    if callback.message and batch:
        try:
            await callback.message.edit_text(
                text=format_report_batch_admin(batch, topics),
                reply_markup=get_admin_batch_detail_keyboard(batch),
            )
        except TelegramBadRequest:
            pass


@router.callback_query(F.data.startswith("arep_del_confirm:"))
async def confirm_delete_batch(callback: CallbackQuery) -> None:
    """Подтверждение удаления партии докладов."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    _, batch_id_raw = callback.data.split(":", 1)
    batch_id = int(batch_id_raw)

    batch = await get_batch_by_id(batch_id, config.DB_PATH)
    if not batch:
        await callback.answer("Партия уже удалена.", show_alert=True)
        return

    text = (
        f"🗑 <b>Удаление партии докладов #{batch_id}</b>\n\n"
        f"Предмет: <b>{html.escape(batch['subject_name'])}</b>\n"
        f"Семинар: <code>{html.escape(batch['seminar_date'])}</code>\n\n"
        "⚠️ Вы уверены? Будут удалены все темы этой партии и отменена задача дропа в планировщике."
    )

    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_admin_confirm_delete_batch_keyboard(batch_id),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith("arep_del_do:"))
async def execute_delete_batch(callback: CallbackQuery) -> None:
    """Удаление партии докладов из БД и отмена задачи в APScheduler."""
    if not _is_admin_check(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    _, batch_id_raw = callback.data.split(":", 1)
    batch_id = int(batch_id_raw)

    # Отменяем задачу в планировщике
    cancel_scheduled_report_job(batch_id)

    # Удаляем из БД (темы удалятся каскадно)
    deleted = await delete_report_batch(batch_id, config.DB_PATH)
    if deleted:
        await callback.answer("Партия докладов успешно удалена! 🗑", show_alert=True)
    else:
        await callback.answer("Партия не найдена.", show_alert=True)

    # Возврат к списку
    batches = await get_all_report_batches(config.DB_PATH)
    if not batches:
        text = "📋 <b>Список партий докладов</b>\n\n<i>Все партии докладов удалены.</i>"
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Запланировать новый дроп",
                        callback_data="arep_menu_add",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="« В меню докладов",
                        callback_data="admin_reports_menu",
                    )
                ],
            ]
        )
    else:
        text = "📋 <b>Список партий докладов:</b>"
        markup = get_admin_batches_list_keyboard(batches)

    if callback.message:
        try:
            await callback.message.edit_text(text=text, reply_markup=markup)
        except TelegramBadRequest:
            pass
