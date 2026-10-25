"""Тесты для модуля расписания, панели старосты и планировщика задач."""

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import CallbackQuery, Chat, Message, User

from bot import config
from bot.database import (
    clear_week_schedule,
    copy_next_to_current_week,
    get_schedule,
    get_schedule_day,
    init_db,
    update_schedule_day,
)
from bot.handlers.admin_schedule import (
    cancel_edit_day,
    clear_single_day,
    close_admin_panel,
    execute_clear_week,
    execute_rollover,
    open_admin_panel,
    open_admin_schedule_menu,
    open_admin_week_days,
    preview_week_schedule,
    process_day_content_input,
    start_edit_day,
)
from bot.handlers.schedule import (
    refresh_schedule_view,
    show_schedule_current_week,
    toggle_schedule_week,
)
from bot.handlers.states import ScheduleAdminStates
from bot.keyboards import (
    get_admin_main_keyboard,
    get_admin_schedule_days_keyboard,
    get_admin_schedule_menu_keyboard,
    get_schedule_view_keyboard,
)
from bot.utils import (
    format_day_preview,
    format_schedule_text,
    get_weekday_name,
    get_weekday_short,
    rollover_weekly_schedule,
    setup_scheduler,
)

TEST_DB_PATH = "test_schedule.db"


class TestScheduleModule(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        await init_db(TEST_DB_PATH)
        config.DB_PATH = TEST_DB_PATH
        config.ADMIN_IDS = [999]
        self.storage = MemoryStorage()

    async def asyncTearDown(self) -> None:
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def _create_mock_message(self, user_id: int, text: str) -> Message:
        msg = MagicMock(spec=Message)
        msg.message_id = 101
        msg.from_user = MagicMock(spec=User)
        msg.from_user.id = user_id
        msg.from_user.username = "test_user"
        msg.text = text
        msg.answer = AsyncMock()
        return msg

    def _create_mock_callback(self, user_id: int, data: str) -> CallbackQuery:
        cb = MagicMock(spec=CallbackQuery)
        cb.from_user = MagicMock(spec=User)
        cb.from_user.id = user_id
        cb.data = data
        cb.answer = AsyncMock()
        cb.message = MagicMock(spec=Message)
        cb.message.message_id = 202
        cb.message.edit_text = AsyncMock()
        cb.message.delete = AsyncMock()
        return cb

    def _get_fsm_context(self, user_id: int) -> FSMContext:
        key = StorageKey(bot_id=1, chat_id=user_id, user_id=user_id)
        return FSMContext(storage=self.storage, key=key)

    # -------------------------------------------------------------
    # 1. Тестирование утилит форматирования
    # -------------------------------------------------------------
    def test_schedule_formatting(self) -> None:
        """Проверка красивого форматирования пустого и заполненного расписания."""
        self.assertEqual(get_weekday_name(1), "Понедельник")
        self.assertEqual(get_weekday_short(1), "Пн")

        # Пустое расписание
        empty_rows = [{"day_of_week": i, "content": ""} for i in range(1, 7)]
        empty_text = format_schedule_text(empty_rows, "current")
        self.assertIn("пока не заполнено", empty_text)

        # Заполненное расписание
        filled_rows = [
            {"day_of_week": 1, "content": "1. 09:00 Психология личности\n2. 10:45 Статистика"},
            {"day_of_week": 2, "content": ""},
            {"day_of_week": 3, "content": ""},
            {"day_of_week": 4, "content": ""},
            {"day_of_week": 5, "content": ""},
            {"day_of_week": 6, "content": ""},
        ]
        text = format_schedule_text(filled_rows, "current")
        self.assertIn("Понедельник", text)
        self.assertIn("09:00 Психология личности", text)
        self.assertIn("Вторник", text)
        self.assertIn("Занятий нет", text)

        preview = format_day_preview(1, "current", "1 пара: Методология")
        self.assertIn("Понедельник", preview)
        self.assertIn("1 пара: Методология", preview)

    # -------------------------------------------------------------
    # 2. Тестирование просмотра студентами
    # -------------------------------------------------------------
    async def test_student_schedule_view(self) -> None:
        """Проверка просмотра расписания и переключения недель студентом."""
        user_id = 123
        msg = self._create_mock_message(user_id, "📅 Расписание")
        await show_schedule_current_week(msg)
        msg.answer.assert_called_once()
        args, kwargs = msg.answer.call_args
        sent_text = kwargs.get("text") or (args[0] if args else "")
        self.assertIn("Текущая неделя", sent_text)

        # Переключение на следующую неделю
        cb = self._create_mock_callback(user_id, "sched_view:next")
        await toggle_schedule_week(cb)
        cb.message.edit_text.assert_called_once()
        self.assertIn("Следующая неделя", cb.message.edit_text.call_args[1]["text"])
        cb.answer.assert_called_once()

        # Обновление
        cb_refresh = self._create_mock_callback(user_id, "sched_refresh:current")
        await refresh_schedule_view(cb_refresh)
        cb_refresh.message.edit_text.assert_called_once()
        cb_refresh.answer.assert_called_once()

    # -------------------------------------------------------------
    # 3. Тестирование панели старосты (Админки)
    # -------------------------------------------------------------
    async def test_admin_access_control(self) -> None:
        """Обычный студент не имеет доступа к панели старосты."""
        student_id = 555
        fsm_ctx = self._get_fsm_context(student_id)
        msg = self._create_mock_message(student_id, "⚙️ Панель старосты")
        await open_admin_panel(msg, fsm_ctx)
        msg.answer.assert_called_once()
        self.assertIn("нет доступа", msg.answer.call_args[0][0])

        cb = self._create_mock_callback(student_id, "admin_sched_menu")
        await open_admin_schedule_menu(cb, fsm_ctx)
        cb.answer.assert_called_once_with("⛔ Нет доступа", show_alert=True)

    async def test_admin_open_and_navigate(self) -> None:
        """Администратор успешно открывает панель и разделы."""
        admin_id = 999
        fsm_ctx = self._get_fsm_context(admin_id)

        msg = self._create_mock_message(admin_id, "⚙️ Панель старосты")
        await open_admin_panel(msg, fsm_ctx)
        msg.answer.assert_called_once()
        self.assertIn("Панель управления старосты", msg.answer.call_args[0][0])

        cb_sched = self._create_mock_callback(admin_id, "admin_sched_menu")
        await open_admin_schedule_menu(cb_sched, fsm_ctx)
        cb_sched.message.edit_text.assert_called_once()
        self.assertIn("Управление расписанием занятий", cb_sched.message.edit_text.call_args[1]["text"])

        cb_days = self._create_mock_callback(admin_id, "admin_sched_week:current")
        await open_admin_week_days(cb_days, fsm_ctx)
        cb_days.message.edit_text.assert_called_once()
        self.assertIn("Текущая неделя", cb_days.message.edit_text.call_args[1]["text"])

    async def test_admin_edit_day_flow(self) -> None:
        """Полный FSM цикл редактирования дня недели старостой."""
        admin_id = 999
        fsm_ctx = self._get_fsm_context(admin_id)

        # 1. Админ нажимает редактировать Понедельник (день 1) текущей недели
        cb_edit = self._create_mock_callback(admin_id, "admin_sched_edit_day:current:1")
        await start_edit_day(cb_edit, fsm_ctx)

        self.assertEqual(await fsm_ctx.get_state(), ScheduleAdminStates.waiting_for_day_content.state)
        fsm_data = await fsm_ctx.get_data()
        self.assertEqual(fsm_data["week_type"], "current")
        self.assertEqual(fsm_data["day_of_week"], 1)

        # 2. Админ отправляет новое расписание сообщением
        msg_input = self._create_mock_message(admin_id, "1. 09:00 Психология личности\n2. 10:45 Экспериментальная психология")
        await process_day_content_input(msg_input, fsm_ctx)

        # FSM состояние сброшено
        self.assertIsNone(await fsm_ctx.get_state())
        msg_input.answer.assert_called_once()
        self.assertIn("успешно сохранено", msg_input.answer.call_args[1]["text"])

        # Проверяем запись в БД
        day_row = await get_schedule_day("current", 1, TEST_DB_PATH)
        self.assertIsNotNone(day_row)
        self.assertIn("Психология личности", day_row["content"])

        # 3. Очистка этого же дня кнопкой
        cb_clear = self._create_mock_callback(admin_id, "admin_sched_clear_day:current:1")
        await clear_single_day(cb_clear, fsm_ctx)
        day_row_cleared = await get_schedule_day("current", 1, TEST_DB_PATH)
        self.assertEqual(day_row_cleared["content"], "")

    async def test_admin_clear_week_and_rollover(self) -> None:
        """Проверка очистки всей недели и ручного переноса."""
        admin_id = 999
        fsm_ctx = self._get_fsm_context(admin_id)

        # Заполняем вторник следующей недели
        await update_schedule_day("next", 2, "2 пара: Психодиагностика", TEST_DB_PATH)

        # Ручной перенос
        cb_roll = self._create_mock_callback(admin_id, "admin_sched_rollover_do")
        await execute_rollover(cb_roll)

        current_day2 = await get_schedule_day("current", 2, TEST_DB_PATH)
        next_day2 = await get_schedule_day("next", 2, TEST_DB_PATH)
        self.assertEqual(current_day2["content"], "2 пара: Психодиагностика")
        self.assertEqual(next_day2["content"], "")

        # Очистка всей текущей недели
        cb_clear_week = self._create_mock_callback(admin_id, "admin_sched_clear_week_do:current")
        await execute_clear_week(cb_clear_week)

        current_day2_after = await get_schedule_day("current", 2, TEST_DB_PATH)
        self.assertEqual(current_day2_after["content"], "")

    # -------------------------------------------------------------
    # 4. Тестирование APScheduler
    # -------------------------------------------------------------
    async def test_scheduler_setup_and_job(self) -> None:
        """Проверка настройки планировщика и выполнения субботней задачи."""
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        sched = setup_scheduler(mock_bot)
        job = sched.get_job("weekly_schedule_rollover")
        self.assertIsNotNone(job)

        # Заполняем следующую неделю в БД
        await update_schedule_day("next", 3, "3 пара: Статистика", TEST_DB_PATH)

        # Запуск функции переноса расписания
        await rollover_weekly_schedule(mock_bot)

        # Проверяем, что в текущей неделе появилась среда, а в следующей пусто
        cur_day3 = await get_schedule_day("current", 3, TEST_DB_PATH)
        nxt_day3 = await get_schedule_day("next", 3, TEST_DB_PATH)
        self.assertEqual(cur_day3["content"], "3 пара: Статистика")
        self.assertEqual(nxt_day3["content"], "")

        # Проверяем, что старосте отправлено уведомление
        mock_bot.send_message.assert_called_once()
        self.assertEqual(mock_bot.send_message.call_args[1]["chat_id"], 999)
        self.assertIn("Плановое обновление расписания", mock_bot.send_message.call_args[1]["text"])


if __name__ == "__main__":
    unittest.main()
