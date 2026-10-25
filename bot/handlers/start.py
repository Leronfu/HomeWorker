"""Обработчик команды /start, регистрации студентов и главного меню."""

import html
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import is_admin
from bot.database import add_or_update_user, get_user
from bot.handlers.states import RegistrationStates
from bot.keyboards import get_main_menu_keyboard

router = Router(name="start_router")


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    """Обработка команды /start.
    
    Если студент запускает бота впервые — запрашиваем Имя и Фамилию.
    Если уже зарегистрирован — сразу открываем Главное меню.
    """
    user_id = message.from_user.id
    username = message.from_user.username
    user = await get_user(user_id)
    admin_flag = is_admin(user_id)

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
        admin_note = "\n\n👑 <i>У вас есть доступ к панели старосты (администратора).</i>" if is_user_admin else ""
        await message.answer(
            f"👋 С возвращением, <b>{html.escape(full_name)}</b>!{admin_note}\n\n"
            "Выбери нужный раздел в меню ниже:",
            reply_markup=get_main_menu_keyboard(is_admin=is_user_admin),
        )
        return

    # Новый пользователь: запрашиваем Имя и Фамилию
    await state.set_state(RegistrationStates.waiting_for_full_name)
    await message.answer(
        "👋 <b>Привет!</b> Я бот-помощник нашей учебной группы по психологии.\n\n"
        "Чтобы староста и одногруппники видели, кто записался на доклад или взял задание, "
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

    admin_note = "\n\n👑 <i>Вам предоставлены права администратора (панель старосты).</i>" if admin_flag else ""

    await message.answer(
        f"✅ <b>Приятно познакомиться, {html.escape(full_name)}!</b> Регистрация завершена.{admin_note}\n\n"
        "Теперь тебе доступны расписание, домашние задания и запись на темы докладов. "
        "Выбирай нужный раздел в меню ниже:",
        reply_markup=get_main_menu_keyboard(is_admin=admin_flag),
    )





