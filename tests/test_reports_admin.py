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
    add_or_update_user,
    auto_assign_remaining_topics,
    claim_topic,
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
    process_custom_subject_input_for_reports,
    process_delete_subject_action,
    process_release_date_input,
    process_seminar_date_input,
    process_topics_list_input,
    ask_custom_subject_for_reports,
    publish_batch_immediately,
    show_admin_batch_detail,
    show_admin_batches_list,
    show_delete_subject_menu,
    start_report_fsm_seminar_date,
)
from bot.handlers.states import ReportAdminStates
from bot.utils import (
    auto_assign_report_batch_job,
    calculate_auto_assign_datetime,
    cancel_scheduled_report_job,
    format_report_batch_admin,
    generate_random_release_datetime,
    notify_admins_report_drop,
    parse_release_date,
    parse_topics_text,
    publish_report_job,
    restore_pending_report_jobs,
    schedule_auto_assign_job,
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
        """Проверка генерации случайного времени строго в окне 12:00:00 - 20:00:00."""
        from datetime import time
        future_date = date(2026, 11, 20)

        # Проверяем 100 генераций для статистической надежности
        for _ in range(100):
            rand_dt = generate_random_release_datetime(future_date)
            self.assertEqual(rand_dt.date(), future_date)
            self.assertEqual(rand_dt.tzinfo, MSK_TZ)
            t = rand_dt.time()
            self.assertGreaterEqual(t, time(12, 0, 0))
            self.assertLessEqual(t, time(20, 0, 0))

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
        self.assertNotIn("14:35:00", text)
        self.assertIn("засекречено", text)
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

    async def test_notify_admins_report_drop(self) -> None:
        """Проверка отправки персонального уведомления администраторам при дропе докладов."""
        b_id = await create_report_batch(
            subject_id=1,
            seminar_date="15.12.2026",
            release_date="10.12.2026",
            release_datetime_random="2026-12-10 14:00:00",
            topics=["Тема 1", "Тема 2", "Тема 3"],
            db_path=TEST_DB_PATH,
        )

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        notified_count = await notify_admins_report_drop(mock_bot, b_id, db_path=TEST_DB_PATH)
        self.assertEqual(notified_count, 1)
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args[1]
        self.assertEqual(call_args["chat_id"], 999)
        self.assertIn("РАНДОМАЙЗЕР ВЫЛОЖИЛ РАБОТЫ!", call_args["text"])
        self.assertIn("Психология эмоций и мотивации", call_args["text"])
        self.assertIn("15.12.2026", call_args["text"])
        self.assertIn("3", call_args["text"])

    async def test_publish_report_job_notifies_admins_and_broadcasts(self) -> None:
        """Проверка, что publish_report_job выполняет и общую рассылку, и уведомление старост."""
        b_id = await create_report_batch(
            subject_id=3,
            seminar_date="20.12.2026",
            release_date="18.12.2026",
            release_datetime_random="2026-12-18 11:30:00",
            topics=["Тема Диагностики"],
            db_path=TEST_DB_PATH,
        )

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        await publish_report_job(mock_bot, b_id)

        # Партия помечена как опубликованная
        b_db = await get_batch_by_id(b_id, TEST_DB_PATH)
        self.assertEqual(b_db["is_published"], 1)

        # Бот отправил сообщения (как минимум админу 999)
        self.assertTrue(mock_bot.send_message.called)
        sent_texts = [call[1]["text"] for call in mock_bot.send_message.call_args_list]
        admin_alert_present = any("РАНДОМАЙЗЕР ВЫЛОЖИЛ РАБОТЫ!" in t for t in sent_texts)
        self.assertTrue(admin_alert_present)

    # -------------------------------------------------------------
    # 6. Авто-распределение неразобранных тем (Шаг 14)
    # -------------------------------------------------------------
    def test_calculate_auto_assign_datetime(self) -> None:
        """Проверка расчета времени авто-раздачи: через 2 дня в 09:50 МСК."""
        target_dt = calculate_auto_assign_datetime("28.10.2026")
        self.assertIsNotNone(target_dt)
        self.assertEqual(target_dt.year, 2026)
        self.assertEqual(target_dt.month, 10)
        self.assertEqual(target_dt.day, 30)
        self.assertEqual(target_dt.hour, 9)
        self.assertEqual(target_dt.minute, 50)
        self.assertEqual(target_dt.second, 0)
        self.assertEqual(target_dt.tzinfo, MSK_TZ)

    async def test_auto_assign_remaining_topics_database(self) -> None:
        """Проверка атомарного случайного распределения оставшихся тем в БД."""
        # 1. Создаем партию докладов
        b_id = await create_report_batch(
            subject_id=2,
            seminar_date="12.11.2026",
            release_date="10.11.2026",
            release_datetime_random="2026-11-10 12:00:00",
            topics=["Тема 1", "Тема 2", "Тема 3"],
            db_path=TEST_DB_PATH,
        )
        await publish_report_batch(b_id, TEST_DB_PATH)

        # 2. Регистрируем 3 студентов
        await add_or_update_user(101, "ivan", "Иван Иванов", db_path=TEST_DB_PATH)
        await add_or_update_user(102, "petr", "Петр Петров", db_path=TEST_DB_PATH)
        await add_or_update_user(103, "anna", "Анна Смирнова", db_path=TEST_DB_PATH)

        # 3. Иван добровольно забирает Тему 1
        topics = await get_batch_topics(b_id, TEST_DB_PATH)
        await claim_topic(topics[0]["id"], 101, TEST_DB_PATH)

        # 4. Запускаем авто-распределение
        res = await auto_assign_remaining_topics(b_id, TEST_DB_PATH)
        self.assertEqual(res["unassigned_count"], 2)
        self.assertEqual(len(res["assigned"]), 2)
        self.assertEqual(res["remaining_unassigned"], 0)

        # Проверяем, что Тема 2 и Тема 3 распределены между Петром и Анной
        assigned_user_ids = {item["student"]["telegram_id"] for item in res["assigned"]}
        self.assertEqual(assigned_user_ids, {102, 103})

        # Проверяем состояние в БД: все 3 темы заняты
        topics_after = await get_batch_topics(b_id, TEST_DB_PATH)
        self.assertTrue(all(t["user_id"] is not None for t in topics_after))

        # Повторный вызов не распределяет ничего
        res_repeat = await auto_assign_remaining_topics(b_id, TEST_DB_PATH)
        self.assertEqual(res_repeat["unassigned_count"], 0)
        self.assertEqual(len(res_repeat["assigned"]), 0)

    async def test_auto_assign_report_batch_job_notifications(self) -> None:
        """Проверка персональных уведомлений студентам и отчета старосте."""
        b_id = await create_report_batch(
            subject_id=1,
            seminar_date="14.11.2026",
            release_date="12.11.2026",
            release_datetime_random="2026-11-12 12:00:00",
            topics=["Экспериментальный метод"],
            db_path=TEST_DB_PATH,
        )
        await publish_report_batch(b_id, TEST_DB_PATH)

        await add_or_update_user(201, "olga", "Ольга Сидорова", db_path=TEST_DB_PATH)

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        res = await auto_assign_report_batch_job(mock_bot, b_id, db_path=TEST_DB_PATH)
        self.assertEqual(len(res["assigned"]), 1)

        # Должно быть отправлено 2 сообщения: 1 студенту 201 и 1 старосте 999
        self.assertEqual(mock_bot.send_message.call_count, 2)
        calls = mock_bot.send_message.call_args_list

        student_call = next(c for c in calls if c[1]["chat_id"] == 201)
        self.assertIn("Вам автоматически назначен доклад!", student_call[1]["text"])
        self.assertIn("Экспериментальный метод", student_call[1]["text"])

        admin_call = next(c for c in calls if c[1]["chat_id"] == 999)
        self.assertIn("ОТЧЕТ ОБ АВТО-РАСПРЕДЕЛЕНИИ ДОКЛАДОВ", admin_call[1]["text"])
        self.assertIn("Ольга Сидорова", admin_call[1]["text"])

    async def test_auto_assign_all_topics_already_claimed(self) -> None:
        """Проверка отчета старосте, когда все темы уже были заняты добровольно."""
        b_id = await create_report_batch(
            subject_id=1,
            seminar_date="16.11.2026",
            release_date="14.11.2026",
            release_datetime_random="2026-11-14 12:00:00",
            topics=["Тема Воли"],
            db_path=TEST_DB_PATH,
        )
        await publish_report_batch(b_id, TEST_DB_PATH)
        topics = await get_batch_topics(b_id, TEST_DB_PATH)
        await add_or_update_user(301, "daria", "Дарья", db_path=TEST_DB_PATH)
        await claim_topic(topics[0]["id"], 301, TEST_DB_PATH)

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        res = await auto_assign_report_batch_job(mock_bot, b_id, db_path=TEST_DB_PATH)
        self.assertEqual(res["unassigned_count"], 0)
        self.assertEqual(len(res["assigned"]), 0)

        # Старосте отправлено уведомление, что все темы были разобраны самостоятельно
        mock_bot.send_message.assert_called_once()
        admin_call = mock_bot.send_message.call_args[1]
        self.assertEqual(admin_call["chat_id"], 999)
        self.assertIn("Все темы докладов разобраны!", admin_call["text"])

    async def test_bot_custom_subject_flow(self) -> None:
        """Проверка добавления нового предмета через бота при создании дропа."""
        state = self._get_fsm_context(999)

        # 1. Нажатие кнопки ввода своего предмета
        cb = self._create_mock_callback(999, "arep_custom_subject")
        await ask_custom_subject_for_reports(cb, state)
        self.assertEqual(await state.get_state(), ReportAdminStates.waiting_for_custom_subject)
        cb.message.edit_text.assert_called_once()
        self.assertIn("Ввод нового предмета", cb.message.edit_text.call_args[1]["text"])

        # 2. Ввод слишком короткого названия
        msg_short = self._create_mock_message(999, "A")
        await process_custom_subject_input_for_reports(msg_short, state)
        msg_short.answer.assert_called_once()
        self.assertIn("слишком короткое", msg_short.answer.call_args[0][0])
        self.assertEqual(await state.get_state(), ReportAdminStates.waiting_for_custom_subject)

        # 3. Ввод валидного названия
        msg_valid = self._create_mock_message(999, "Нейробиология поведения")
        await process_custom_subject_input_for_reports(msg_valid, state)
        self.assertEqual(await state.get_state(), ReportAdminStates.waiting_for_seminar_date)
        data = await state.get_data()
        self.assertEqual(data["subject_name"], "Нейробиология поведения")
        self.assertGreater(data["subject_id"], 0)

    async def test_bot_delete_subject_flow(self) -> None:
        """Проверка меню и действия удаления предмета через бота."""
        state = self._get_fsm_context(999)

        # 1. Открытие меню удаления предметов
        cb_menu = self._create_mock_callback(999, "arep_menu_delete_subject")
        await show_delete_subject_menu(cb_menu, state)
        cb_menu.message.edit_text.assert_called_once()
        self.assertIn("Удаление предмета", cb_menu.message.edit_text.call_args[1]["text"])

        # 2. Попытка удаления предмета, к которому привязан батч
        b_id = await create_report_batch(
            subject_id=1,
            seminar_date="16.11.2026",
            release_date="14.11.2026",
            release_datetime_random="2026-11-14 12:00:00",
            topics=["Тема"],
            db_path=TEST_DB_PATH,
        )
        cb_del_fail = self._create_mock_callback(999, "arep_do_del_subj:1")
        await process_delete_subject_action(cb_del_fail)
        cb_del_fail.answer.assert_called_once()
        self.assertIn("Нельзя удалить", cb_del_fail.answer.call_args[0][0])

        # 3. Удаление предмета без привязанных записей
        # Создадим отдельный свободный предмет
        from bot.database import get_or_create_subject
        free_subj = await get_or_create_subject("Лишний предмет", TEST_DB_PATH)
        free_id = free_subj["id"]

        cb_del_ok = self._create_mock_callback(999, f"arep_do_del_subj:{free_id}")
        await process_delete_subject_action(cb_del_ok)
        cb_del_ok.answer.assert_called_once()
        self.assertIn("удален", cb_del_ok.answer.call_args[0][0])



if __name__ == "__main__":
    unittest.main()
