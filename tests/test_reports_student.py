"""Тесты для модуля «Доклады — Часть 2: Рассылка и запись студентов» (Шаг 7)."""

import os
import unittest
from unittest.mock import AsyncMock, MagicMock

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import CallbackQuery, Message, User

from bot import config
from bot.database import (
    add_or_update_user,
    claim_topic,
    create_report_batch,
    get_batch_by_id,
    get_batch_topics,
    init_db,
    publish_report_batch,
)
from bot.handlers.reports import (
    back_to_reports_subjects,
    process_claim_topic,
    process_unclaim_topic,
    refresh_report_batch_topics,
    show_reports_subjects_menu,
    show_subject_reports,
    view_report_batch_topics,
)
from bot.utils import (
    broadcast_report_drop,
    format_report_batch_student,
)

TEST_DB_PATH = "test_reports_student.db"


class TestReportsStudentModule(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        await init_db(TEST_DB_PATH)
        config.DB_PATH = TEST_DB_PATH
        config.ADMIN_IDS = [999]
        self.storage = MemoryStorage()

        # Регистрируем двух тестовых студентов
        await add_or_update_user(101, "anna_s", "Анна Смирнова", False, TEST_DB_PATH)
        await add_or_update_user(102, "petr_p", "Петр Петров", False, TEST_DB_PATH)

    async def asyncTearDown(self) -> None:
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def _create_mock_message(self, user_id: int, text: str) -> Message:
        msg = MagicMock(spec=Message)
        msg.message_id = 701
        msg.from_user = MagicMock(spec=User)
        msg.from_user.id = user_id
        msg.from_user.username = f"user_{user_id}"
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
        cb.message.message_id = 802
        cb.message.edit_text = AsyncMock()
        return cb

    # -------------------------------------------------------------
    # 1. Форматирование карточки тем для студента
    # -------------------------------------------------------------
    def test_format_report_batch_student(self) -> None:
        """Проверка форматирования списка тем с разделением на свободные и занятые."""
        batch = {
            "id": 1,
            "subject_name": "Психология личности",
            "seminar_date": "15.11.2026",
        }
        topics = [
            {"topic_number": 1, "topic_text": "Теория личности Фрейда", "user_id": 101, "student_name": "Анна Смирнова"},
            {"topic_number": 2, "topic_text": "Гуманистическая теория Роджерса", "user_id": None, "student_name": None},
        ]

        # Для Анны (она заняла тему 1)
        text_anna = format_report_batch_student(batch, topics, user_id=101)
        self.assertIn("Психология личности", text_anna)
        self.assertIn("15.11.2026", text_anna)
        self.assertIn("1 из 2", text_anna)
        self.assertIn("🌟 <b>Занято вами (Анна Смирнова)</b>", text_anna)
        self.assertIn("🟢 Свободно", text_anna)

        # Для Петра (для него тема 1 занята Анной)
        text_petr = format_report_batch_student(batch, topics, user_id=102)
        self.assertIn("✅ Занято (<b>Анна Смирнова</b>)", text_petr)

    # -------------------------------------------------------------
    # 2. Пользовательский сценарий студента: просмотр тем
    # -------------------------------------------------------------
    async def test_student_view_reports(self) -> None:
        """Проверка перехода в раздел докладов и просмотра тем."""
        user_id = 101

        # 1. Студент жмет «🎤 Доклады»
        msg_menu = self._create_mock_message(user_id, "🎤 Доклады")
        await show_reports_subjects_menu(msg_menu)
        msg_menu.answer.assert_called_once()
        self.assertIn("Выберите предмет", msg_menu.answer.call_args[0][0])

        # 2. Выбор предмета 1, когда доклады еще НЕ опубликованы
        cb_subj_empty = self._create_mock_callback(user_id, "rep_subj:1")
        await show_subject_reports(cb_subj_empty)
        cb_subj_empty.message.edit_text.assert_called_once()
        self.assertIn("пока нет открытых тем", cb_subj_empty.message.edit_text.call_args[1]["text"])

        # 3. Создаем и публикуем партию докладов
        b_id = await create_report_batch(
            subject_id=1,
            seminar_date="18.11.2026",
            release_date="16.11.2026",
            release_datetime_random="2026-11-16 12:00:00",
            topics=["Тема эмоций 1", "Тема эмоций 2"],
            db_path=TEST_DB_PATH,
        )
        await publish_report_batch(b_id, TEST_DB_PATH)

        # 4. Студент снова открывает предмет 1 -> видит список тем и кнопки
        cb_subj_published = self._create_mock_callback(user_id, "rep_subj:1")
        await show_subject_reports(cb_subj_published)
        cb_subj_published.message.edit_text.assert_called_once()
        self.assertIn("Тема эмоций 1", cb_subj_published.message.edit_text.call_args[1]["text"])
        self.assertIn("2 из 2", cb_subj_published.message.edit_text.call_args[1]["text"])

        # 5. Возврат к предметам
        cb_back = self._create_mock_callback(user_id, "rep_list_subjects")
        await back_to_reports_subjects(cb_back)
        cb_back.message.edit_text.assert_called_once()

    # -------------------------------------------------------------
    # 3. Запись на тему, защита от коллизий и отказ от темы
    # -------------------------------------------------------------
    async def test_claim_unclaim_and_race_condition(self) -> None:
        """Проверка бронирования темы, защиты от одновременных кликов и отказа."""
        def _get_alert(cb):
            args, kwargs = cb.answer.call_args
            return kwargs.get("text") or (args[0] if args else "")

        b_id = await create_report_batch(
            subject_id=2,
            seminar_date="20.11.2026",
            release_date="17.11.2026",
            release_datetime_random="2026-11-17 14:00:00",
            topics=["Вопрос A", "Вопрос B"],
            db_path=TEST_DB_PATH,
        )
        await publish_report_batch(b_id, TEST_DB_PATH)

        topics = await get_batch_topics(b_id, TEST_DB_PATH)
        topic_a_id = topics[0]["id"]
        topic_b_id = topics[1]["id"]

        # 1. Анна занимает тему A
        cb_anna = self._create_mock_callback(101, f"rep_claim:{topic_a_id}:{b_id}")
        await process_claim_topic(cb_anna)
        cb_anna.answer.assert_called_once()
        self.assertIn("успешно закреплена", _get_alert(cb_anna))

        # Проверяем, что в БД за темой A закреплена Анна
        topics_after_anna = await get_batch_topics(b_id, TEST_DB_PATH)
        self.assertEqual(topics_after_anna[0]["user_id"], 101)
        self.assertEqual(topics_after_anna[0]["student_name"], "Анна Смирнова")

        # 2. Петр пытается занять ТУ ЖЕ тему A (получает отказ с алертом)
        cb_petr = self._create_mock_callback(102, f"rep_claim:{topic_a_id}:{b_id}")
        await process_claim_topic(cb_petr)
        cb_petr.answer.assert_called_once()
        self.assertIn("только что забрал другой студент", _get_alert(cb_petr))

        # 3. Анна пытается занять еще одну тему B в этой же партии (ограничение 1 тема на студента)
        cb_anna_second = self._create_mock_callback(101, f"rep_claim:{topic_b_id}:{b_id}")
        await process_claim_topic(cb_anna_second)
        cb_anna_second.answer.assert_called_once()
        self.assertIn("Вы уже заняли тему", _get_alert(cb_anna_second))

        # 4. Петр занимает свободную тему B
        cb_petr_b = self._create_mock_callback(102, f"rep_claim:{topic_b_id}:{b_id}")
        await process_claim_topic(cb_petr_b)
        cb_petr_b.answer.assert_called_once()
        self.assertIn("успешно закреплена", _get_alert(cb_petr_b))

        # 5. Анна отказывается от своей темы A
        cb_anna_unclaim = self._create_mock_callback(101, f"rep_unclaim:{topic_a_id}:{b_id}")
        await process_unclaim_topic(cb_anna_unclaim)
        cb_anna_unclaim.answer.assert_called_once()
        self.assertIn("успешно освободили", _get_alert(cb_anna_unclaim))

        # Проверяем в БД: тема A снова свободна
        topics_after_unclaim = await get_batch_topics(b_id, TEST_DB_PATH)
        self.assertIsNone(topics_after_unclaim[0]["user_id"])

        # 6. Незарегистрированный пользователь пытается взять тему
        unreg_user_id = 777
        cb_unreg = self._create_mock_callback(unreg_user_id, f"rep_claim:{topic_a_id}:{b_id}")
        await process_claim_topic(cb_unreg)
        cb_unreg.answer.assert_called_once()
        self.assertIn("сначала введите свои Имя и Фамилию", _get_alert(cb_unreg))

    # -------------------------------------------------------------
    # 4. Массовая рассылка (Broadcast)
    # -------------------------------------------------------------
    async def test_broadcast_report_drop(self) -> None:
        """Проверка отправки рассылки всем пользователям при дропе."""
        b_id = await create_report_batch(
            subject_id=3,
            seminar_date="22.11.2026",
            release_date="20.11.2026",
            release_datetime_random="2026-11-20 15:30:00",
            topics=["Психодиагностический тест 1"],
            db_path=TEST_DB_PATH,
        )

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        sent_count = await broadcast_report_drop(mock_bot, b_id)
        # В БД 2 пользователя (Анна и Петр)
        self.assertEqual(sent_count, 2)
        self.assertEqual(mock_bot.send_message.call_count, 2)

        # Проверяем текст рассылки
        first_call_args, first_call_kwargs = mock_bot.send_message.call_args_list[0]
        text_sent = first_call_kwargs.get("text", "")
        self.assertIn("ВЫЛОЖЕНЫ ТЕМЫ ДОКЛАДОВ", text_sent)
        self.assertIn("22.11.2026", text_sent)


if __name__ == "__main__":
    unittest.main()
