"""Тесты для модуля «Доклады — Часть 1: Создание и планирование (Админка)» (Шаг 6)."""

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
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import CallbackQuery, Message, User

from bot import config
from bot.database import (
    create_report_batch,
    delete_report_batch,
    get_all_report_batches,
    get_batch_by_id,
    get_batch_topics,
    get_pending_report_batches,
    init_db,
    publish_report_batch,
)
from bot.handlers.admin_reports import (
    choose_subject_for_reports,
    confirm_delete_batch,
    execute_delete_batch,
    open_admin_reports_menu,
    process_release_date_input,
    process_seminar_date_input,
    process_topics_list_input,
    publish_batch_immediately,
    show_admin_batch_detail,
    show_admin_batches_list,
    start_report_fsm_seminar_date,
)
from bot.handlers.states import ReportAdminStates
from bot.utils import (
    cancel_scheduled_report_job,
    format_report_batch_admin,
    generate_random_release_datetime,
    parse_release_date,
    parse_topics_text,
    publish_report_job,
    restore_pending_report_jobs,
    schedule_report_release,
    scheduler,
)
from bot.utils.report_helpers import MSK_TZ

TEST_DB_PATH = "test_reports_admin.db"


class TestReportsAdminModule(unittest.IsolatedAsyncioTestCase):
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
        msg.message_id = 501
        msg.from_user = MagicMock(spec=User)
        msg.from_user.id = user_id
        msg.from_user.username = "test_starosta"
        msg.text = text
        msg.answer = AsyncMock()
        msg.bot = MagicMock()
        msg.bot.send_message = AsyncMock()
        return msg

    def _create_mock_callback(self, user_id: int, data: str) -> CallbackQuery:
        cb = MagicMock(spec=CallbackQuery)
        cb.from_user = MagicMock(spec=User)
        cb.from_user.id = user_id
        cb.data = data
        cb.answer = AsyncMock()
        cb.bot = MagicMock()
        cb.bot.send_message = AsyncMock()
        cb.message = MagicMock(spec=Message)
        cb.message.message_id = 602
        cb.message.edit_text = AsyncMock()
        return cb

    def _get_fsm_context(self, user_id: int) -> FSMContext:
        key = StorageKey(bot_id=1, chat_id=user_id, user_id=user_id)
        return FSMContext(storage=self.storage, key=key)

    # -------------------------------------------------------------
    # 1. Тестирование утилит парсинга и генерации времени
    # -------------------------------------------------------------
    def test_parse_topics_text(self) -> None:
        """Проверка очистки нумерации и парсинга тем из текста."""
        raw_text = (
            "1. Теория базовых эмоций Изарда\n"
            "2) Психофизиология стресса по Селье\n"
            "- Эмоциональный интеллект Гоулмана\n"
            "• Теория дифференциальных эмоций\n"
            "  \n"
            "Мотивация достижения Макклелланда\n"
        )
        topics = parse_topics_text(raw_text)
        self.assertEqual(len(topics), 5)
        self.assertEqual(topics[0], "Теория базовых эмоций Изарда")
        self.assertEqual(topics[1], "Психофизиология стресса по Селье")
        self.assertEqual(topics[2], "Эмоциональный интеллект Гоулмана")
        self.assertEqual(topics[3], "Теория дифференциальных эмоций")
        self.assertEqual(topics[4], "Мотивация достижения Макклелланда")

    def test_parse_release_date(self) -> None:
        """Проверка парсинга дат различных форматов."""
        d1 = parse_release_date("28.10.2026")
        self.assertIsNotNone(d1)
        self.assertEqual(d1, date(2026, 10, 28))

        d2 = parse_release_date("2026-11-05")
        self.assertIsNotNone(d2)
        self.assertEqual(d2, date(2026, 11, 5))

        # Невалидная дата
        d_bad = parse_release_date("не дата")
        self.assertIsNone(d_bad)

    def test_generate_random_release_datetime(self) -> None:
        """Проверка генерации случайного времени в дневном окне 10:00 - 20:59."""
        future_date = date(2026, 11, 20)
        rand_dt = generate_random_release_datetime(future_date)
        self.assertEqual(rand_dt.date(), future_date)
        self.assertGreaterEqual(rand_dt.hour, 10)
        self.assertLessEqual(rand_dt.hour, 20)
        self.assertEqual(rand_dt.tzinfo, MSK_TZ)

    def test_format_report_batch_admin(self) -> None:
        """Проверка карточки предпросмотра партии для старосты."""
        batch = {
            "id": 1,
            "subject_name": "Психология личности",
            "seminar_date": "15.11.2026",
            "release_date": "10.11.2026",
            "release_datetime_random": "2026-11-10 14:35:00",
            "is_published": False,
        }
        topics = [
            {"topic_number": 1, "topic_text": "Теория Фрейда", "student_name": None},
            {"topic_number": 2, "topic_text": "Теория Юнга", "student_name": "Иван Иванов"},
        ]
        text = format_report_batch_admin(batch, topics)
        self.assertIn("Психология личности", text)
        self.assertIn("15.11.2026", text)
        self.assertIn("Запланирован дроп", text)
        self.assertIn("14:35:00", text)
        self.assertIn("1. Теория Фрейда — 🟢 Свободно", text)
        self.assertIn("2. Теория Юнга — ✅ Занято (<b>Иван Иванов</b>)", text)

    # -------------------------------------------------------------
    # 2. База данных: get_all_report_batches
    # -------------------------------------------------------------
    async def test_get_all_report_batches_db(self) -> None:
        """Проверка получения списка всех партий со счетчиком тем."""
        b_id = await create_report_batch(
            subject_id=1,
            seminar_date="12.11.2026",
            release_date="10.11.2026",
            release_datetime_random="2026-11-10 15:00:00",
            topics=["Тема 1", "Тема 2", "Тема 3"],
            db_path=TEST_DB_PATH,
        )
        batches = await get_all_report_batches(TEST_DB_PATH)
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0]["id"], b_id)
        self.assertEqual(batches[0]["topics_count"], 3)
        self.assertEqual(batches[0]["claimed_count"], 0)
        self.assertEqual(batches[0]["is_published"], 0)

    # -------------------------------------------------------------
    # 3. Полный FSM-сценарий создания дропа докладов
    # -------------------------------------------------------------
    async def test_admin_create_report_batch_flow(self) -> None:
        """Проверка пошагового создания партии докладов старостой."""
        admin_id = 999
        fsm_ctx = self._get_fsm_context(admin_id)

        # 1. Открытие раздела докладов
        cb_menu = self._create_mock_callback(admin_id, "admin_reports_menu")
        await open_admin_reports_menu(cb_menu, fsm_ctx)
        cb_menu.message.edit_text.assert_called_once()
        self.assertIn("Управление докладами", cb_menu.message.edit_text.call_args[1]["text"])

        # 2. Нажатие «Запланировать новый дроп» -> выбор предмета
        cb_add = self._create_mock_callback(admin_id, "arep_menu_add")
        await choose_subject_for_reports(cb_add, fsm_ctx)
        cb_add.message.edit_text.assert_called_once()
        self.assertIn("Выберите предмет", cb_add.message.edit_text.call_args[1]["text"])

        # 3. Выбор предмета #1 («Психология эмоций и мотивации»)
        cb_pick_subj = self._create_mock_callback(admin_id, "arep_pick_subj:1")
        await start_report_fsm_seminar_date(cb_pick_subj, fsm_ctx)
        self.assertEqual(await fsm_ctx.get_state(), ReportAdminStates.waiting_for_seminar_date.state)
        cb_pick_subj.message.edit_text.assert_called_once()
        self.assertIn("Шаг 1 из 3", cb_pick_subj.message.edit_text.call_args[1]["text"])

        # 4. Ввод даты семинара
        msg_sem = self._create_mock_message(admin_id, "25 ноября 2026")
        await process_seminar_date_input(msg_sem, fsm_ctx)
        self.assertEqual(await fsm_ctx.get_state(), ReportAdminStates.waiting_for_topics_list.state)
        msg_sem.answer.assert_called_once()
        self.assertIn("Шаг 2 из 3", msg_sem.answer.call_args[1]["text"])

        # 5. Отправка тем докладов
        topics_input = (
            "1. Эмоциональные теории\n"
            "2. Теория Джеймса-Ланге\n"
            "3. Когнитивный подход к эмоциям"
        )
        msg_topics = self._create_mock_message(admin_id, topics_input)
        await process_topics_list_input(msg_topics, fsm_ctx)
        self.assertEqual(await fsm_ctx.get_state(), ReportAdminStates.waiting_for_release_date.state)
        msg_topics.answer.assert_called_once()
        self.assertIn("Успешно распознано тем: 3", msg_topics.answer.call_args[1]["text"])

        # 6. Ввод даты честного дропа
        msg_rel = self._create_mock_message(admin_id, "20.11.2026")
        await process_release_date_input(msg_rel, fsm_ctx)

        # FSM состояние сброшено
        self.assertIsNone(await fsm_ctx.get_state())
        msg_rel.answer.assert_called_once()
        self.assertIn("успешно запланирован", msg_rel.answer.call_args[1]["text"])

        # Проверяем запись в БД
        batches = await get_all_report_batches(TEST_DB_PATH)
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0]["seminar_date"], "25 ноября 2026")
        self.assertEqual(batches[0]["topics_count"], 3)
        self.assertEqual(batches[0]["is_published"], 0)

        # Проверяем, что задача зарегистрирована в APScheduler
        job = scheduler.get_job(f"report_batch_{batches[0]['id']}")
        self.assertIsNotNone(job)

    # -------------------------------------------------------------
    # 4. Просмотр карточки, публикация сейчас и удаление
    # -------------------------------------------------------------
    async def test_admin_manage_report_batches(self) -> None:
        """Проверка списка, карточки, ручной публикации и удаления партии."""
        admin_id = 999
        fsm_ctx = self._get_fsm_context(admin_id)

        # Создаем партию
        b_id = await create_report_batch(
            subject_id=2,
            seminar_date="30.11.2026",
            release_date="28.11.2026",
            release_datetime_random="2026-11-28 16:20:00",
            topics=["Вопрос 1", "Вопрос 2"],
            db_path=TEST_DB_PATH,
        )

        # 1. Список партий
        cb_list = self._create_mock_callback(admin_id, "arep_menu_list")
        await show_admin_batches_list(cb_list, fsm_ctx)
        cb_list.message.edit_text.assert_called_once()
        self.assertIn("Список партий докладов", cb_list.message.edit_text.call_args[1]["text"])

        # 2. Карточка партии
        cb_detail = self._create_mock_callback(admin_id, f"arep_detail:{b_id}")
        await show_admin_batch_detail(cb_detail, fsm_ctx)
        cb_detail.message.edit_text.assert_called_once()
        self.assertIn(f"Партия докладов #{b_id}", cb_detail.message.edit_text.call_args[1]["text"])

        # 3. Ручная немедленная публикация
        cb_pub = self._create_mock_callback(admin_id, f"arep_pub_now:{b_id}")
        await publish_batch_immediately(cb_pub)
        cb_pub.answer.assert_called_once()

        batch_published = await get_batch_by_id(b_id, TEST_DB_PATH)
        self.assertEqual(batch_published["is_published"], 1)

        # 4. Запрос подтверждения удаления
        cb_del_conf = self._create_mock_callback(admin_id, f"arep_del_confirm:{b_id}")
        await confirm_delete_batch(cb_del_conf)
        cb_del_conf.message.edit_text.assert_called_once()
        self.assertIn("Вы уверены?", cb_del_conf.message.edit_text.call_args[1]["text"])

        # 5. Выполнение удаления
        cb_del_do = self._create_mock_callback(admin_id, f"arep_del_do:{b_id}")
        await execute_delete_batch(cb_del_do)
        cb_del_do.answer.assert_called_once()

        # Проверяем отсутствие партии в БД
        batch_deleted = await get_batch_by_id(b_id, TEST_DB_PATH)
        self.assertIsNone(batch_deleted)

    # -------------------------------------------------------------
    # 5. Восстановление задач при перезапуске (APScheduler)
    # -------------------------------------------------------------
    async def test_restore_pending_report_jobs(self) -> None:
        """Проверка восстановления отложенных задач из БД."""
        future_dt_str = (datetime.now(MSK_TZ) + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        past_dt_str = (datetime.now(MSK_TZ) - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")

        # 1. Будущий дроп
        b_future = await create_report_batch(
            subject_id=1,
            seminar_date="10.12.2026",
            release_date="08.12.2026",
            release_datetime_random=future_dt_str,
            topics=["Тема A"],
            db_path=TEST_DB_PATH,
        )

        # 2. Просроченный дроп (бот был выключен в момент наступления времени)
        b_past = await create_report_batch(
            subject_id=2,
            seminar_date="05.12.2026",
            release_date="03.12.2026",
            release_datetime_random=past_dt_str,
            topics=["Тема B"],
            db_path=TEST_DB_PATH,
        )

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        restored_count = await restore_pending_report_jobs(mock_bot)
        self.assertEqual(restored_count, 2)

        # Будущая задача должна быть в планировщике
        job_future = scheduler.get_job(f"report_batch_{b_future}")
        self.assertIsNotNone(job_future)

        # Просроченная задача должна быть сразу опубликована
        batch_past_db = await get_batch_by_id(b_past, TEST_DB_PATH)
        self.assertEqual(batch_past_db["is_published"], 1)


if __name__ == "__main__":
    unittest.main()
