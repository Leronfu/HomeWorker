"""Обработчик команды /start, регистрации студентов и запуска Telegram Mini App."""

import html
import logging
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import MenuButtonWebApp, Message, WebAppInfo

from bot import config
from bot.config import is_admin
from bot.database import add_or_update_user, get_user
from bot.handlers.states import RegistrationStates
from bot.keyboards import get_main_menu_keyboard, get_webapp_inline_keyboard

logger = logging.getLogger(__name__)
router = Router(name="start_router")


async def _set_user_menu_button(message: Message, user_id: int) -> None:
    """Установка персональной кнопки меню Telegram (MenuButtonWebApp)."""
    try:
        url = config.WEB_APP_URL or "http://localhost:8080"
        await message.bot.set_chat_menu_button(
            chat_id=user_id,
            menu_button=MenuButtonWebApp(text="HomeWorker", web_app=WebAppInfo(url=url)),
        )
    except Exception as e:
        logger.debug("Не удалось установить MenuButton для %s: %s", user_id, e)


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    """Обработка команды /start."""
    user_id = message.from_user.id
    username = message.from_user.username
    user = await get_user(user_id)
    admin_flag = is_admin(user_id)

    # Настраиваем постоянную кнопку Mini App в строке ввода
    await _set_user_menu_button(message, user_id)

    # Если пользователь уже зарегистрирован с именем
    if user and user.get("full_name"):
        full_name = user["full_name"]
        is_user_admin = admin_flag or bool(user.get("is_admin", 0))
        # Обновляем username и права администратора
        await add_or_update_user(
            telegram_id=user_id,
            username=username,
            full_name=full_name,
            is_admin=is_user_admin,
        )
        await state.clear()
        admin_note = "\n👑 <i>Вам доступна панель старосты внутри приложения.</i>" if is_user_admin else ""
        await message.answer(
            f"👋 С возвращением, <b>{html.escape(full_name)}</b>!{admin_note}\n\n"
            "Все материалы группы (Расписание, ДЗ, Доклады и Админка) "
            "доступны в интерактивном приложении <b>Telegram Mini App</b>.\n\n"
            "Нажмите на кнопку ниже для входа 👇",
            reply_markup=get_webapp_inline_keyboard("📱 Открыть HomeWorker"),
        )
        return

    # Новый пользователь: запрашиваем Имя и Фамилию
    await state.set_state(RegistrationStates.waiting_for_full_name)
    await message.answer(
        "👋 <b>Привет!</b> Я помощник учебной группы факультета психологии.\n\n"
        "Чтобы одногруппники и староста видели, кто берет темы докладов и задания, "
        "напиши свои <b>Имя и Фамилию</b> (например: <i>Иван Иванов</i>):"
    )


@router.message(RegistrationStates.waiting_for_full_name, F.text)
async def process_full_name(message: Message, state: FSMContext) -> None:
    """Обработка ввода Имени и Фамилии студента."""
    full_name = message.text.strip()

    # Простейшая валидация на осмысленность ввода
    if len(full_name) < 3 or full_name.isdigit():
        await message.answer(
            "⚠️ Пожалуйста, введи свои настоящие Имя и Фамилию словами (например: <i>Анна Смирнова</i>):"
        )
        return

    user_id = message.from_user.id
    username = message.from_user.username
    admin_flag = is_admin(user_id)

    # Сохраняем в базу данных
    await add_or_update_user(
        telegram_id=user_id,
        username=username,
        full_name=full_name,
        is_admin=admin_flag,
    )
    await state.clear()
    await _set_user_menu_button(message, user_id)

    admin_note = "\n\n👑 <i>Вам предоставлены права администратора (панель старосты).</i>" if admin_flag else ""

    await message.answer(
        f"✅ <b>Приятно познакомиться, {html.escape(full_name)}!</b> Регистрация завершена.{admin_note}\n\n"
        "Теперь тебе доступны расписание, домашние задания и система честного дропа тем докладов.\n\n"
        "Запускай приложение по кнопке ниже:",
        reply_markup=get_webapp_inline_keyboard("🚀 Запустить HomeWorker"),
    )


@router.message(F.text)
async def handle_any_text(message: Message) -> None:
    """Перенаправление любых сообщений и текстовых кнопок на запуск Mini App."""
    user_id = message.from_user.id
    is_user_admin = is_admin(user_id)
    admin_note = "\n👑 <i>Вам доступен режим старосты внутри приложения.</i>" if is_user_admin else ""

    await message.answer(
        "🎓 <b>HomeWorker — Психология</b>\n\n"
        "Все разделы нашей группы (расписание пар, домашние задания, честный дроп тем докладов и управление) "
        "работают внутри интерактивного <b>Telegram Mini App</b>!\n\n"
        f"Нажмите кнопку ниже, чтобы открыть приложение 👇{admin_note}",
        reply_markup=get_webapp_inline_keyboard("📱 Открыть HomeWorker"),
    )
