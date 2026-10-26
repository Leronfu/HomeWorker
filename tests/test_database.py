"""Тестирование инициализации и операций с базой данных."""

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

import asyncio
import unittest
from bot.database import (
    DEFAULT_SUBJECTS,
    init_db,
    add_or_update_user,
    get_user,
    get_all_users,
    set_user_admin,
    get_all_subjects,
    get_or_create_subject,
    delete_subject,
    get_schedule,
    update_schedule_day,
    copy_next_to_current_week,
    add_homework,
    get_homework_by_subject,
    delete_homework,
    create_report_batch,
    get_pending_report_batches,
    publish_report_batch,
    get_batches_by_subject,
    get_batch_topics,
    claim_topic,
    unclaim_topic,
)

TEST_DB_PATH = "test_homeworker.db"


class TestDatabase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        await init_db(TEST_DB_PATH)

    async def asyncTearDown(self) -> None:
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    async def test_init_and_subjects(self) -> None:
        """Проверка автозаполнения 10 предметов при создании БД."""
        subjects = await get_all_subjects(TEST_DB_PATH)
        self.assertEqual(len(subjects), 10)
        subject_names = [s["name"] for s in subjects]
        self.assertEqual(subject_names, DEFAULT_SUBJECTS)

    async def test_users(self) -> None:
        """Проверка регистрации и обновления пользователей."""
        await add_or_update_user(
            telegram_id=123456,
            username="ivan_ivanov",
            full_name="Иван Иванов",
            is_admin=False,
            db_path=TEST_DB_PATH,
        )
        user = await get_user(123456, TEST_DB_PATH)
        self.assertIsNotNone(user)
        self.assertEqual(user["full_name"], "Иван Иванов")
        self.assertEqual(user["is_admin"], 0)

        # Обновление имени
        await add_or_update_user(
            telegram_id=123456,
            username="ivan_updated",
            full_name="Иван Петров",
            is_admin=False,
            db_path=TEST_DB_PATH,
        )
        user = await get_user(123456, TEST_DB_PATH)
        self.assertEqual(user["full_name"], "Иван Петров")
        self.assertEqual(user["username"], "ivan_updated")

        # Назначение админом
        await set_user_admin(123456, True, TEST_DB_PATH)
        user = await get_user(123456, TEST_DB_PATH)
        self.assertEqual(user["is_admin"], 1)

        users = await get_all_users(TEST_DB_PATH)
        self.assertEqual(len(users), 1)

    async def test_schedule(self) -> None:
        """Проверка редактирования расписания и переноса следующей недели на текущую."""
        current_sched = await get_schedule("current", TEST_DB_PATH)
        self.assertEqual(len(current_sched), 6)  # Пн-Сб
        self.assertEqual(current_sched[0]["content"], "")

        # Обновляем понедельник следующей недели
        await update_schedule_day("next", 1, "1 пара: Статистика", TEST_DB_PATH)
        next_sched = await get_schedule("next", TEST_DB_PATH)
        self.assertEqual(next_sched[0]["content"], "1 пара: Статистика")

        # Перенос следующей недели в текущую
        await copy_next_to_current_week(TEST_DB_PATH)
        current_sched = await get_schedule("current", TEST_DB_PATH)
        next_sched = await get_schedule("next", TEST_DB_PATH)

        self.assertEqual(current_sched[0]["content"], "1 пара: Статистика")
        self.assertEqual(next_sched[0]["content"], "")

    async def test_homework(self) -> None:
        """Проверка добавления, чтения и удаления ДЗ."""
        hw_id = await add_homework(
            subject_id=1,
            due_date="15.11.2026",
            task_text="Прочитать главу 3, ответить на вопросы",
            db_path=TEST_DB_PATH,
        )
        self.assertGreater(hw_id, 0)

        hw_list = await get_homework_by_subject(1, TEST_DB_PATH)
        self.assertEqual(len(hw_list), 1)
        self.assertEqual(hw_list[0]["task_text"], "Прочитать главу 3, ответить на вопросы")

        deleted = await delete_homework(hw_id, TEST_DB_PATH)
        self.assertTrue(deleted)
        hw_list_after = await get_homework_by_subject(1, TEST_DB_PATH)
        self.assertEqual(len(hw_list_after), 0)

    async def test_reports_and_claiming(self) -> None:
        """Проверка системы докладов и атомарного закрепления темы."""
        await add_or_update_user(
            telegram_id=111,
            username="stud1",
            full_name="Студент 1",
            db_path=TEST_DB_PATH,
        )
        await add_or_update_user(
            telegram_id=222,
            username="stud2",
            full_name="Студент 2",
            db_path=TEST_DB_PATH,
        )

        topics = [
            "Теория эмоций Джеймса-Ланге",
            "Мотивация достижения по Макклелланду",
            "Когнитивные теории эмоций",
        ]
        batch_id = await create_report_batch(
            subject_id=1,
            seminar_date="20.11.2026",
            release_date="18.11.2026",
            release_datetime_random="2026-11-18 14:35:00",
            topics=topics,
            db_path=TEST_DB_PATH,
        )
        self.assertGreater(batch_id, 0)

        # Проверка списка ожидающих дропов
        pending = await get_pending_report_batches(TEST_DB_PATH)
        self.assertEqual(len(pending), 1)

        # Публикация
        await publish_report_batch(batch_id, TEST_DB_PATH)
        published_batches = await get_batches_by_subject(1, only_published=True, db_path=TEST_DB_PATH)
        self.assertEqual(len(published_batches), 1)

        batch_topics = await get_batch_topics(batch_id, TEST_DB_PATH)
        self.assertEqual(len(batch_topics), 3)
        self.assertIsNone(batch_topics[0]["user_id"])

        first_topic_id = batch_topics[0]["id"]

        # Студент 1 занимает тему
        claimed_first = await claim_topic(first_topic_id, 111, TEST_DB_PATH)
        self.assertTrue(claimed_first)

        # Студент 2 пытается занять ту же тему (должен получить отказ)
        claimed_second = await claim_topic(first_topic_id, 222, TEST_DB_PATH)
        self.assertFalse(claimed_second)

        # Проверяем, что за темой закреплен студент 1
        updated_topics = await get_batch_topics(batch_id, TEST_DB_PATH)
        self.assertEqual(updated_topics[0]["user_id"], 111)
        self.assertEqual(updated_topics[0]["student_name"], "Студент 1")

        # Студент 1 отказывается от темы
        unclaimed = await unclaim_topic(first_topic_id, 111, TEST_DB_PATH)
        self.assertTrue(unclaimed)

        # Теперь тема свободна, и студент 2 может ее взять
        claimed_by_2 = await claim_topic(first_topic_id, 222, TEST_DB_PATH)
        self.assertTrue(claimed_by_2)

    async def test_add_and_delete_subject(self) -> None:
        """Проверка добавления и безопасного удаления предметов."""
        # 1. Добавление предмета
        new_subj = await get_or_create_subject("Нейропсихология", TEST_DB_PATH)
        new_id = new_subj["id"]
        self.assertGreater(new_id, 0)

        # 2. Повторное добавление того же имени возвращает существующий ID
        same_subj = await get_or_create_subject("  Нейропсихология  ", TEST_DB_PATH)
        self.assertEqual(new_id, same_subj["id"])

        subjects = await get_all_subjects(TEST_DB_PATH)
        self.assertIn("Нейропсихология", [s["name"] for s in subjects])

        # 3. Удаление предмета без связанных записей
        ok_del, _ = await delete_subject(new_id, force=False, db_path=TEST_DB_PATH)
        self.assertTrue(ok_del)
        subjects_after = await get_all_subjects(TEST_DB_PATH)
        self.assertNotIn("Нейропсихология", [s["name"] for s in subjects_after])

        # 4. Создаем предмет со связанным докладом
        subj_with_rep = await get_or_create_subject("Когнитивистика", TEST_DB_PATH)
        subj_id = subj_with_rep["id"]
        await create_report_batch(
            subject_id=subj_id,
            seminar_date="20.12.2026",
            release_date="19.12.2026",
            release_datetime_random="2026-12-19 12:00:00",
            topics=["Тема когнитивистики"],
            db_path=TEST_DB_PATH,
        )

        # Попытка удалить без force должна вернуть (False, сообщение)
        ok_fail, fail_msg = await delete_subject(subj_id, force=False, db_path=TEST_DB_PATH)
        self.assertFalse(ok_fail)
        self.assertIn("привязано", fail_msg)

        # Удаление с force=True разрешено
        ok_forced, _ = await delete_subject(subj_id, force=True, db_path=TEST_DB_PATH)
        self.assertTrue(ok_forced)



if __name__ == "__main__":
    unittest.main()
