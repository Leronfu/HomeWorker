"""Обработчики раздела «Доклады» для студентов (Шаг 7)."""

import html
import logging
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import config
from bot.database import (
    claim_topic,
    get_all_subjects,
    get_batch_by_id,
    get_batch_topics,
    get_batches_by_subject,
    get_subject_by_id,
    get_user,
    unclaim_topic,
)
from bot.handlers.states import ReportStudentStates
from bot.keyboards import (
    get_student_batch_topics_keyboard,
    get_student_batches_choice_keyboard,
    get_subjects_keyboard,
)
from bot.utils import format_report_batch_student

logger = logging.getLogger("ReportsHandler")
router = Router(name="reports_router")


# =====================================================================
# Вход в раздел докладов и выбор дисциплины
# =====================================================================

@router.message(F.text == "🎤 Доклады")
async def show_reports_subjects_menu(message: Message) -> None:
    """Вывод списка предметов при нажатии кнопки «🎤 Доклады» в Главном меню."""
    try:
        subjects = await get_all_subjects(config.DB_PATH)
        await message.answer(
            "🎤 <b>Темы докладов учебной группы</b>\n\n"
            "Выберите предмет из списка ниже, чтобы посмотреть опубликованные доклады и занять тему:",
            reply_markup=get_subjects_keyboard(subjects, callback_prefix="rep_subj"),
        )
    except Exception as e:
        logger.error("Ошибка при открытии раздела докладов: %s", e, exc_info=True)
        await message.answer("⚠️ Не удалось загрузить список предметов. Попробуйте чуть позже.")


@router.callback_query(F.data == "rep_list_subjects")
async def back_to_reports_subjects(callback: CallbackQuery) -> None:
    """Возврат к списку предметов из экрана тем докладов."""
    try:
        subjects = await get_all_subjects(config.DB_PATH)
        if callback.message:
            await callback.message.edit_text(
                "🎤 <b>Темы докладов учебной группы</b>\n\n"
                "Выберите предмет из списка ниже, чтобы посмотреть опубликованные доклады и занять тему:",
                reply_markup=get_subjects_keyboard(subjects, callback_prefix="rep_subj"),
            )
        await callback.answer()
    except TelegramBadRequest:
        await callback.answer()
    except Exception as e:
        logger.error("Ошибка при возврате к списку предметов: %s", e, exc_info=True)
        await callback.answer("⚠️ Произошла ошибка.", show_alert=True)


# =====================================================================
# Просмотр партий докладов по предмету
# =====================================================================

@router.callback_query(F.data.startswith("rep_subj:"))
async def show_subject_reports(callback: CallbackQuery) -> None:
    """Отображение опубликованных докладов по выбранному предмету."""
    try:
        _, subj_id_raw = callback.data.split(":", 1)
        subject_id = int(subj_id_raw)

        subject = await get_subject_by_id(subject_id, config.DB_PATH)
        if not subject:
            await callback.answer("Предмет не найден.", show_alert=True)
            return

        # Получаем только ОПУБЛИКОВАННЫЕ партии докладов
        batches = await get_batches_by_subject(subject_id, only_published=True, db_path=config.DB_PATH)
        subject_name = subject["name"]

        if not batches:
            text = (
                f"🎤 <b>Доклады: {html.escape(subject_name)}</b>\n\n"
                "🎉 <i>По этому предмету пока нет открытых тем докладов.\n"
                "Ожидайте честного дропа от старосты — вам придёт уведомление в бота!</i>"
            )
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="« К списку предметов",
                            callback_data="rep_list_subjects",
                        )
                    ]
                ]
            )
            if callback.message:
                await callback.message.edit_text(text=text, reply_markup=markup)
            await callback.answer()
            return

        # Если опубликована 1 партия — сразу показываем её темы
        if len(batches) == 1:
            batch = batches[0]
            batch_id = batch["id"]
            topics = await get_batch_topics(batch_id, config.DB_PATH)
            text = format_report_batch_student(batch, topics, user_id=callback.from_user.id)
            markup = get_student_batch_topics_keyboard(batch_id, topics, user_id=callback.from_user.id)

            if callback.message:
                await callback.message.edit_text(text=text, reply_markup=markup)
            await callback.answer()
            return

        # Если опубликовано несколько партий на разные даты — даем выбрать дату семинара
        text = (
            f"🎤 <b>Доклады: {html.escape(subject_name)}</b>\n\n"
            "Найдено несколько партий докладов. Выберите дату интересующего семинара:"
        )
        markup = get_student_batches_choice_keyboard(batches)
        if callback.message:
            await callback.message.edit_text(text=text, reply_markup=markup)
        await callback.answer()

    except TelegramBadRequest:
        await callback.answer()
    except Exception as e:
        logger.error("Ошибка при отображении докладов по предмету: %s", e, exc_info=True)
        await callback.answer("⚠️ Не удалось загрузить доклады.", show_alert=True)


@router.callback_query(F.data.startswith("rep_view_batch:"))
async def view_report_batch_topics(callback: CallbackQuery) -> None:
    """Прямой просмотр конкретной партии докладов (в т.ч. по кнопке из рассылки)."""
    try:
        _, batch_id_raw = callback.data.split(":", 1)
        batch_id = int(batch_id_raw)

        batch = await get_batch_by_id(batch_id, config.DB_PATH)
        if not batch or not batch.get("is_published"):
            await callback.answer("Темы ещё не опубликованы или партия была удалена.", show_alert=True)
            return

        topics = await get_batch_topics(batch_id, config.DB_PATH)
        text = format_report_batch_student(batch, topics, user_id=callback.from_user.id)
        markup = get_student_batch_topics_keyboard(batch_id, topics, user_id=callback.from_user.id)

        if callback.message:
            await callback.message.edit_text(text=text, reply_markup=markup)
        await callback.answer()

    except TelegramBadRequest:
        await callback.answer()
    except Exception as e:
        logger.error("Ошибка при открытии партии докладов %s: %s", callback.data, e, exc_info=True)
        await callback.answer("⚠️ Не удалось загрузить темы.", show_alert=True)


# =====================================================================
# Атомарное бронирование темы студентом (защита от одновременного клика)
# =====================================================================

@router.callback_query(F.data.startswith("rep_claim:"))
async def process_claim_topic(callback: CallbackQuery, state: Optional[FSMContext] = None) -> None:
    """Обработка нажатия на кнопку свободной темы."""
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    topic_id = int(parts[1])
    batch_id = int(parts[2])

    try:
        # 1. Проверяем регистрацию пользователя (наличие Имени и Фамилии)
        user = await get_user(user_id, config.DB_PATH)
        if not user or not user.get("full_name"):
            await callback.answer(
                "⚠️ Чтобы занять тему, сначала введите свои Имя и Фамилию с помощью команды /start!",
                show_alert=True,
            )
            return

        # 2. Проверяем, не занял ли студент УЖЕ какую-либо тему в этой партии
        current_topics = await get_batch_topics(batch_id, config.DB_PATH)
        already_claimed = next((t for t in current_topics if t.get("user_id") == user_id), None)
        if already_claimed:
            await callback.answer(
                f"⚠️ Вы уже заняли тему №{already_claimed['topic_number']} в этой партии!\n"
                "Сначала откажитесь от неё кнопкой ниже, если хотите выбрать другую тему.",
                show_alert=True,
            )
            return

        batch = await get_batch_by_id(batch_id, config.DB_PATH)
        if not batch:
            await callback.answer("Партия докладов не найдена.", show_alert=True)
            return

        # Если доклад групповой, запрашиваем список участников группы через FSM
        if batch.get("report_type") == "group":
            topic = next((t for t in current_topics if t.get("id") == topic_id), None)
            topic_text = topic["topic_text"] if topic else "Выбранная тема"

            await state.set_state(ReportStudentStates.waiting_for_group_members)
            await state.update_data(topic_id=topic_id, batch_id=batch_id)

            prompt = (
                f"👥 <b>Вы выбрали групповой доклад!</b>\n"
                f"📝 <b>Тема:</b> «{html.escape(topic_text)}»\n\n"
                "Отправьте сообщением <b>Имена и Фамилии всех участников вашей группы</b> (через запятую):\n"
                f"<i>Например: {html.escape(user['full_name'])}, Петр Сидоров</i>"
            )
            if callback.message:
                await callback.message.answer(text=prompt)
            await callback.answer()
            return

        # 3. Атомарное закрепление индивидуального доклада в БД
        success = await claim_topic(topic_id, user_id, db_path=config.DB_PATH)

        if not success:
            # Кто-то успел на долю секунды раньше!
            await callback.answer(
                "⚡ Упс! Эту тему только что забрал другой студент!\n"
                "Пожалуйста, выберите другую свободную тему из списка.",
                show_alert=True,
            )
        else:
            await callback.answer(
                "🎉 Поздравляем! Тема успешно закреплена за вами!",
                show_alert=True,
            )

        # 4. Мгновенно обновляем экран
        updated_topics = await get_batch_topics(batch_id, config.DB_PATH)

        if callback.message and batch:
            text = format_report_batch_student(batch, updated_topics, user_id=user_id)
            markup = get_student_batch_topics_keyboard(batch_id, updated_topics, user_id=user_id)
            await callback.message.edit_text(text=text, reply_markup=markup)

    except TelegramBadRequest:
        pass
    except Exception as e:
        logger.error("Ошибка при бронировании темы #%s: %s", topic_id, e, exc_info=True)
        await callback.answer("⚠️ Произошла ошибка при бронировании темы.", show_alert=True)


@router.message(ReportStudentStates.waiting_for_group_members, F.text)
async def process_group_members_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода состава группы студентом при записи на групповой доклад."""
    user_id = message.from_user.id
    members_text = message.text.strip()
    if not members_text or len(members_text) < 3:
        await message.answer("⚠️ Пожалуйста, введите корректный список участников группы (например: Иван Иванов, Петр Сидоров):")
        return

    data = await state.get_data()
    topic_id = data.get("topic_id")
    batch_id = data.get("batch_id")
    await state.clear()

    if not topic_id or not batch_id:
        await message.answer("⚠️ Сессия записи устарела. Пожалуйста, откройте доклады заново.")
        return

    success = await claim_topic(topic_id, user_id, group_members=members_text, db_path=config.DB_PATH)
    if not success:
        await message.answer(
            "⚡ <b>Упс! Эту тему только что забрал другой студент или группа!</b>\n"
            "Пожалуйста, перейдите в раздел «🎤 Доклады» и выберите другую свободную тему."
        )
        return

    await message.answer(
        f"🎉 <b>Групповой доклад успешно закреплен за вашей группой!</b>\n\n"
        f"👥 <b>Участники группы:</b>\n{html.escape(members_text)}\n\n"
        "<i>Вы можете посмотреть статус темы в разделе «🎤 Доклады».</i>"
    )


# =====================================================================
# Отказ от своей темы
# =====================================================================

@router.callback_query(F.data.startswith("rep_unclaim:"))
async def process_unclaim_topic(callback: CallbackQuery) -> None:
    """Освобождение темы, если студент передумал или нажал случайно."""
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    topic_id = int(parts[1])
    batch_id = int(parts[2])

    try:
        success = await unclaim_topic(topic_id, user_id, config.DB_PATH)
        if success:
            await callback.answer(
                "✅ Вы успешно освободили тему! Теперь она снова доступна для других студентов.",
                show_alert=True,
            )
        else:
            await callback.answer("Не удалось освободить тему.", show_alert=True)

        batch = await get_batch_by_id(batch_id, config.DB_PATH)
        updated_topics = await get_batch_topics(batch_id, config.DB_PATH)

        if callback.message and batch:
            text = format_report_batch_student(batch, updated_topics, user_id=user_id)
            markup = get_student_batch_topics_keyboard(batch_id, updated_topics, user_id=user_id)
            await callback.message.edit_text(text=text, reply_markup=markup)

    except TelegramBadRequest:
        pass
    except Exception as e:
        logger.error("Ошибка при отказе от темы #%s: %s", topic_id, e, exc_info=True)
        await callback.answer("⚠️ Ошибка при отмене бронирования.", show_alert=True)


# =====================================================================
# Ручное обновление экрана тем
# =====================================================================

@router.callback_query(F.data.startswith("rep_refresh:"))
async def refresh_report_batch_topics(callback: CallbackQuery) -> None:
    """Обновление экрана тем докладов."""
    user_id = callback.from_user.id
    _, batch_id_raw = callback.data.split(":", 1)
    batch_id = int(batch_id_raw)

    try:
        batch = await get_batch_by_id(batch_id, config.DB_PATH)
        if not batch:
            await callback.answer("Партия докладов не найдена.", show_alert=True)
            return

        topics = await get_batch_topics(batch_id, config.DB_PATH)
        text = format_report_batch_student(batch, topics, user_id=user_id)
        markup = get_student_batch_topics_keyboard(batch_id, topics, user_id=user_id)

        if callback.message:
            await callback.message.edit_text(text=text, reply_markup=markup)
        await callback.answer("🔄 Список тем обновлен!")

    except TelegramBadRequest:
        await callback.answer("Данные актуальны 👍")
    except Exception as e:
        logger.error("Ошибка при обновлении тем докладов: %s", e, exc_info=True)
        await callback.answer("⚠️ Не удалось обновить список.", show_alert=True)
