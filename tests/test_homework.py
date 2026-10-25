"""Тесты для модуля «Домашнее задание» (Студенческий просмотр и Админка)."""

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
from aiogram.types import CallbackQuery, Message, User

from bot import config
from bot.database import (
    add_homework,
    delete_homework,
    get_all_subjects,
    get_homework_by_id,
    get_homework_by_subject,
    init_db,
    update_homework,
)
from bot.handlers.admin_homework import (
    choose_subject_to_add_homework,
    choose_subject_to_view_homework,
    confirm_delete_homework,
    execute_delete_homework,
    open_admin_homework_menu,
    process_due_date_input,
    process_edit_due_date_input,
    process_edit_task_text_input,
    process_task_text_input,
    show_admin_homework_detail,
    show_admin_subject_homework_list,
    start_add_homework_flow,
    start_edit_homework_date,
    start_edit_homework_text,
)
from bot.handlers.homework import (
    back_to_homework_subjects,
    refresh_subject_homework,
    show_homework_subjects_menu,
    show_subject_homework,
)
from bot.handlers.states import HomeworkAdminStates
from bot.utils import (
    format_homework_detail_admin,
    format_homework_list_student,
)

TEST_DB_PATH = "test_homework_mod.db"


class TestHomeworkModule(unittest.IsolatedAsyncioTestCase):
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
        msg.message_id = 301
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
        cb.message.message_id = 402
        cb.message.edit_text = AsyncMock()
        return cb

    def _get_fsm_context(self, user_id: int) -> FSMContext:
        key = StorageKey(bot_id=1, chat_id=user_id, user_id=user_id)
        return FSMContext(storage=self.storage, key=key)

    # -------------------------------------------------------------
    # 1. Тестирование утилит форматирования
    # -------------------------------------------------------------
    def test_homework_formatting(self) -> None:
        """Проверка форматирования текста заданий для студентов и админки."""
        # Пустой список
        empty_text = format_homework_list_student("Статистика", [])
        self.assertIn("Статистика", empty_text)
        self.assertIn("пока нет", empty_text)

        # Непустой список
        hw_items = [
            {"id": 1, "due_date": "10.11.2026", "task_text": "Решить задачи 1-5"},
            {"id": 2, "due_date": "15.11.2026", "task_text": "Прочитать главу 2"},
        ]
        formatted = format_homework_list_student("Статистика", hw_items)
        self.assertIn("Всего заданий: 2", formatted)
        self.assertIn("10.11.2026", formatted)
        self.assertIn("Решить задачи 1-5", formatted)
        self.assertIn("Прочитать главу 2", formatted)

        # Детальная карточка админа
        detail = format_homework_detail_admin({
            "id": 10,
            "subject_name": "Психодиагностика",
            "due_date": "20.11.2026",
            "task_text": "Подготовить опросник",
        })
        self.assertIn("Управление заданием #10", detail)
        self.assertIn("Психодиагностика", detail)
        self.assertIn("Подготовить опросник", detail)

    # -------------------------------------------------------------
    # 2. Тестирование базы данных: update_homework
    # -------------------------------------------------------------
    async def test_db_update_homework(self) -> None:
        """Проверка обновления ДЗ в базе данных."""
        hw_id = await add_homework(1, "01.11.2026", "Старый текст", TEST_DB_PATH)
        self.assertGreater(hw_id, 0)

        # Обновление текста
        res1 = await update_homework(hw_id, task_text="Новый текст", db_path=TEST_DB_PATH)
        self.assertTrue(res1)
        record1 = await get_homework_by_id(hw_id, TEST_DB_PATH)
        self.assertEqual(record1["task_text"], "Новый текст")
        self.assertEqual(record1["due_date"], "01.11.2026")

        # Обновление дедлайна
        res2 = await update_homework(hw_id, due_date="05.11.2026", db_path=TEST_DB_PATH)
        self.assertTrue(res2)
        record2 = await get_homework_by_id(hw_id, TEST_DB_PATH)
        self.assertEqual(record2["due_date"], "05.11.2026")

        # Обновление обоих полей
        res3 = await update_homework(hw_id, due_date="12.11.2026", task_text="Финальный текст", db_path=TEST_DB_PATH)
        self.assertTrue(res3)
        record3 = await get_homework_by_id(hw_id, TEST_DB_PATH)
        self.assertEqual(record3["due_date"], "12.11.2026")
        self.assertEqual(record3["task_text"], "Финальный текст")

        # Несуществующий id
        res_none = await update_homework(9999, task_text="Не существует", db_path=TEST_DB_PATH)
        self.assertFalse(res_none)

    # -------------------------------------------------------------
    # 3. Пользовательский сценарий студента
    # -------------------------------------------------------------
    async def test_student_homework_flow(self) -> None:
        """Проверка сценария студента: выбор предмета, просмотр заданий, возврат."""
        user_id = 111

        # Добавим тестовое задание по предмету 1
        await add_homework(1, "20.11.2026", "Выучить классификацию эмоций", TEST_DB_PATH)

        # 1. Нажатие «📚 Домашнее задание»
        msg_menu = self._create_mock_message(user_id, "📚 Домашнее задание")
        await show_homework_subjects_menu(msg_menu)
        msg_menu.answer.assert_called_once()
        self.assertIn("Выберите предмет", msg_menu.answer.call_args[0][0])

        # 2. Выбор предмета 1
        cb_subj = self._create_mock_callback(user_id, "hw_subj:1")
        await show_subject_homework(cb_subj)
        cb_subj.message.edit_text.assert_called_once()
        self.assertIn("Выучить классификацию эмоций", cb_subj.message.edit_text.call_args[1]["text"])
        cb_subj.answer.assert_called_once()

        # 3. Обновление текущего экрана заданий
        cb_refresh = self._create_mock_callback(user_id, "hw_refresh:1")
        await refresh_subject_homework(cb_refresh)
        cb_refresh.message.edit_text.assert_called_once()
        cb_refresh.answer.assert_called_once()

        # 4. Возврат к списку предметов
        cb_back = self._create_mock_callback(user_id, "hw_list_subjects")
        await back_to_homework_subjects(cb_back)
        cb_back.message.edit_text.assert_called_once()
        self.assertIn("Выберите предмет", cb_back.message.edit_text.call_args[0][0])

    # -------------------------------------------------------------
    # 4. Панель старосты (Админка): Добавление ДЗ
    # -------------------------------------------------------------
    async def test_admin_add_homework_flow(self) -> None:
        """Проверка FSM-потока добавления нового ДЗ старостой."""
        admin_id = 999
        fsm_ctx = self._get_fsm_context(admin_id)

        # 1. Открытие меню управления ДЗ
        cb_menu = self._create_mock_callback(admin_id, "admin_hw_menu")
        await open_admin_homework_menu(cb_menu, fsm_ctx)
        cb_menu.message.edit_text.assert_called_once()
        self.assertIn("Управление домашними заданиями", cb_menu.message.edit_text.call_args[1]["text"])

        # 2. Выбор пункта «Добавить ДЗ»
        cb_add = self._create_mock_callback(admin_id, "ahw_menu_add")
        await choose_subject_to_add_homework(cb_add, fsm_ctx)
        cb_add.message.edit_text.assert_called_once()
        self.assertIn("Выберите предмет", cb_add.message.edit_text.call_args[1]["text"])

        # 3. Выбор предмета (например, предмет #2 «Психология личности»)
        cb_pick_subj = self._create_mock_callback(admin_id, "ahw_start_add:2")
        await start_add_homework_flow(cb_pick_subj, fsm_ctx)
        self.assertEqual(await fsm_ctx.get_state(), HomeworkAdminStates.waiting_for_due_date.state)
        cb_pick_subj.message.edit_text.assert_called_once()
        self.assertIn("Шаг 1 из 2", cb_pick_subj.message.edit_text.call_args[1]["text"])

        # 4. Ввод даты сдачи
        msg_date = self._create_mock_message(admin_id, "18.11.2026")
        await process_due_date_input(msg_date, fsm_ctx)
        self.assertEqual(await fsm_ctx.get_state(), HomeworkAdminStates.waiting_for_task_text.state)
        msg_date.answer.assert_called_once()
        self.assertIn("Шаг 2 из 2", msg_date.answer.call_args[0][0])

        # 5. Ввод текста задания
        msg_task = self._create_mock_message(admin_id, "Прочитать лекцию о чертах личности, составить конспект.")
        await process_task_text_input(msg_task, fsm_ctx)

        # Состояние сброшено
        self.assertIsNone(await fsm_ctx.get_state())
        msg_task.answer.assert_called_once()
        self.assertIn("успешно опубликовано", msg_task.answer.call_args[1]["text"])

        # Проверяем запись в БД
        hw_list = await get_homework_by_subject(2, TEST_DB_PATH)
        self.assertEqual(len(hw_list), 1)
        self.assertEqual(hw_list[0]["due_date"], "18.11.2026")
        self.assertIn("составить конспект", hw_list[0]["task_text"])

    # -------------------------------------------------------------
    # 5. Панель старосты (Админка): Редактирование и Удаление ДЗ
    # -------------------------------------------------------------
    async def test_admin_edit_and_delete_homework(self) -> None:
        """Проверка редактирования текста, даты и удаления задания."""
        admin_id = 999
        fsm_ctx = self._get_fsm_context(admin_id)

        # Создаем задание для проверки
        hw_id = await add_homework(3, "10.11.2026", "Исходный тест задания", TEST_DB_PATH)

        # 1. Просмотр списка заданий по предмету 3
        cb_list = self._create_mock_callback(admin_id, "ahw_list_subj:3")
        await show_admin_subject_homework_list(cb_list, fsm_ctx)
        cb_list.message.edit_text.assert_called_once()
        self.assertIn("Управление ДЗ", cb_list.message.edit_text.call_args[1]["text"])

        # 2. Открытие карточки задания
        cb_detail = self._create_mock_callback(admin_id, f"ahw_detail:{hw_id}")
        await show_admin_homework_detail(cb_detail, fsm_ctx)
        cb_detail.message.edit_text.assert_called_once()
        self.assertIn(f"Управление заданием #{hw_id}", cb_detail.message.edit_text.call_args[1]["text"])

        # 3. Редактирование текста задания
        cb_edit_txt = self._create_mock_callback(admin_id, f"ahw_edit_text:{hw_id}")
        await start_edit_homework_text(cb_edit_txt, fsm_ctx)
        self.assertEqual(await fsm_ctx.get_state(), HomeworkAdminStates.waiting_for_edit_task_text.state)

        msg_new_text = self._create_mock_message(admin_id, "Обновленный подробный текст задания")
        await process_edit_task_text_input(msg_new_text, fsm_ctx)
        self.assertIsNone(await fsm_ctx.get_state())

        hw_after_text = await get_homework_by_id(hw_id, TEST_DB_PATH)
        self.assertEqual(hw_after_text["task_text"], "Обновленный подробный текст задания")

        # 4. Редактирование дедлайна задания
        cb_edit_dt = self._create_mock_callback(admin_id, f"ahw_edit_date:{hw_id}")
        await start_edit_homework_date(cb_edit_dt, fsm_ctx)
        self.assertEqual(await fsm_ctx.get_state(), HomeworkAdminStates.waiting_for_edit_due_date.state)

        msg_new_dt = self._create_mock_message(admin_id, "25.11.2026")
        await process_edit_due_date_input(msg_new_dt, fsm_ctx)
        self.assertIsNone(await fsm_ctx.get_state())

        hw_after_dt = await get_homework_by_id(hw_id, TEST_DB_PATH)
        self.assertEqual(hw_after_dt["due_date"], "25.11.2026")

        # 5. Запрос подтверждения удаления
        cb_del_conf = self._create_mock_callback(admin_id, f"ahw_del_confirm:{hw_id}")
        await confirm_delete_homework(cb_del_conf)
        cb_del_conf.message.edit_text.assert_called_once()
        self.assertIn("Вы действительно хотите удалить", cb_del_conf.message.edit_text.call_args[1]["text"])

        # 6. Выполнение удаления
        cb_del_do = self._create_mock_callback(admin_id, f"ahw_del_do:{hw_id}:3")
        await execute_delete_homework(cb_del_do)
        cb_del_do.answer.assert_called_once()

        # Проверяем, что задание удалено из БД
        hw_deleted = await get_homework_by_id(hw_id, TEST_DB_PATH)
        self.assertIsNone(hw_deleted)


if __name__ == "__main__":
    unittest.main()
