"""Тесты для обработчиков, FSM-регистрации и клавиатур Главного меню."""

import os
import sys

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if sys.prefix == sys.base_prefix:
    _venv_py = os.path.join(_project_root, ".venv", "bin", "python3")
    if os.path.exists(_venv_py) and os.path.abspath(sys.executable) != os.path.abspath(_venv_py):
        if "unittest" in sys.argv[0]:
            args = [_venv_py, "-m", "unittest"] + sys.argv[1:]
        elif "-m " in sys.argv[0]:
            mod = sys.argv[0].split("-m ", 1)[1].strip()
            args = [_venv_py, "-m", mod] + sys.argv[1:]
        else:
            args = [_venv_py] + sys.argv
        os.execv(_venv_py, args)

import unittest
from unittest.mock import AsyncMock, MagicMock

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import Chat, Message, User

from bot import config
from bot.database import get_user, init_db
from bot.handlers.start import handle_start, process_full_name
from bot.handlers.states import RegistrationStates
from bot.keyboards import get_main_menu_keyboard

TEST_DB_PATH = "test_handlers.db"


class TestStartAndRegistration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        await init_db(TEST_DB_PATH)
        config.DB_PATH = TEST_DB_PATH
        config.ADMIN_IDS = [999999]
        self.storage = MemoryStorage()

    async def asyncTearDown(self) -> None:
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def _create_mock_message(self, user_id: int, username: str, text: str) -> Message:
        msg = MagicMock(spec=Message)
        msg.from_user = MagicMock(spec=User)
        msg.from_user.id = user_id
        msg.from_user.username = username
        msg.text = text
        msg.answer = AsyncMock()
        msg.bot = MagicMock()
        msg.bot.set_chat_menu_button = AsyncMock()
        return msg

    def _get_fsm_context(self, user_id: int) -> FSMContext:
        key = StorageKey(bot_id=1, chat_id=user_id, user_id=user_id)
        return FSMContext(storage=self.storage, key=key)

    def test_keyboards(self) -> None:
        """Проверка кнопок для открытия Telegram Mini App."""
        kb = get_main_menu_keyboard(is_admin=False)
        buttons = [btn.text for row in kb.keyboard for btn in row]
        self.assertIn("📱 Открыть приложение", buttons)
        self.assertIn("ℹ️ Помощь и статус бота", buttons)

        # Проверка наличия web_app параметра у главной кнопки
        app_btn = kb.keyboard[0][0]
        self.assertIsNotNone(app_btn.web_app)

    async def test_new_user_registration_flow(self) -> None:
        """Проверка полного FSM-цикла регистрации нового студента."""
        user_id = 10001
        fsm_ctx = self._get_fsm_context(user_id)

        # 1. Студент нажимает /start
        msg_start = self._create_mock_message(user_id, "anna_s", "/start")
        await handle_start(msg_start, fsm_ctx)

        # Бот должен запросить имя и перевести в состояние waiting_for_full_name
        current_state = await fsm_ctx.get_state()
        self.assertEqual(current_state, RegistrationStates.waiting_for_full_name.state)
        msg_start.answer.assert_called_once()
        self.assertIn("напиши свои <b>Имя и Фамилию</b>", msg_start.answer.call_args[0][0])

        # 2. Студент вводит слишком короткое имя
        msg_short = self._create_mock_message(user_id, "anna_s", "а")
        await process_full_name(msg_short, fsm_ctx)
        msg_short.answer.assert_called_once()
        self.assertIn("Пожалуйста, введи свои настоящие Имя и Фамилию", msg_short.answer.call_args[0][0])

        # Состояние должно остаться прежним
        self.assertEqual(await fsm_ctx.get_state(), RegistrationStates.waiting_for_full_name.state)

        # 3. Студент вводит корректное имя
        msg_valid = self._create_mock_message(user_id, "anna_s", "Анна Смирнова")
        await process_full_name(msg_valid, fsm_ctx)

        # Состояние сброшено
        self.assertIsNone(await fsm_ctx.get_state())
        msg_valid.answer.assert_called_once()
        self.assertIn("Регистрация завершена", msg_valid.answer.call_args[0][0])

        # Пользователь сохранен в БД
        db_user = await get_user(user_id, TEST_DB_PATH)
        self.assertIsNotNone(db_user)
        self.assertEqual(db_user["full_name"], "Анна Смирнова")
        self.assertEqual(db_user["username"], "anna_s")
        self.assertEqual(db_user["is_admin"], 0)

        # 4. Повторный вызов /start уже зарегистрированным пользователем
        msg_returning = self._create_mock_message(user_id, "anna_s", "/start")
        await handle_start(msg_returning, fsm_ctx)
        msg_returning.answer.assert_called_once()
        self.assertIn("С возвращением, <b>Анна Смирнова</b>!", msg_returning.answer.call_args[0][0])

    async def test_admin_registration(self) -> None:
        """Проверка автоматического назначения администратором при регистрации."""
        admin_id = 999999
        fsm_ctx = self._get_fsm_context(admin_id)

        msg_start = self._create_mock_message(admin_id, "starosta", "/start")
        await handle_start(msg_start, fsm_ctx)

        msg_name = self._create_mock_message(admin_id, "starosta", "Мария Староста")
        await process_full_name(msg_name, fsm_ctx)

        db_admin = await get_user(admin_id, TEST_DB_PATH)
        self.assertIsNotNone(db_admin)
        self.assertEqual(db_admin["is_admin"], 1)
        self.assertIn("панель старосты", msg_name.answer.call_args[0][0])

    async def test_any_text_redirect_to_webapp(self) -> None:
        """Проверка перенаправления любых текстовых сообщений на Mini App."""
        from bot.handlers.start import handle_any_text
        msg = self._create_mock_message(10001, "student", "Покажи расписание")
        await handle_any_text(msg)
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        self.assertIn("HomeWorker — Психология", text)
        self.assertIn("Telegram Mini App", text)
        markup = msg.answer.call_args[1]["reply_markup"]
        self.assertIsNotNone(markup.inline_keyboard[0][0].web_app)


if __name__ == "__main__":
    unittest.main()
