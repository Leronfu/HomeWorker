"""Тесты для REST API встроенного веб-сервера Telegram Mini App (aiohttp)."""

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
import json
import unittest
from unittest.mock import AsyncMock, MagicMock
from aiohttp import streams, web
from aiohttp.test_utils import make_mocked_request

from bot import config
from bot.database import init_db
from bot.web.auth import generate_mock_init_data, validate_telegram_init_data
from bot.web.routes import (
    handle_auth_me,
    handle_claim_topic,
    handle_create_homework,
    handle_create_reports_batch,
    handle_create_subject,
    handle_delete_homework,
    handle_delete_reports_batch,
    handle_delete_subject,
    handle_download_homework_file,
    handle_get_homework,
    handle_get_reports_batches,
    handle_get_schedule,
    handle_get_subjects,
    handle_health,
    handle_publish_reports_batch,
    handle_spin_random_topic,
    handle_unclaim_topic,
    handle_update_homework,
    handle_update_schedule_day,
)
from bot.web.server import BOT_KEY, create_web_app

TEST_DB_PATH = "test_web_api.db"
TEST_ADMIN_ID = 999888
TEST_STUDENT_ID = 111222
TEST_BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


class TestWebApi(unittest.IsolatedAsyncioTestCase):
    """Набор тестов для REST API встроенного сервера Telegram Mini App."""

    async def asyncSetUp(self):
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

        self.orig_token = config.BOT_TOKEN
        self.orig_admin_ids = config.ADMIN_IDS
        self.orig_db_path = config.DB_PATH

        config.BOT_TOKEN = TEST_BOT_TOKEN
        config.ADMIN_IDS = [TEST_ADMIN_ID]
        config.DB_PATH = TEST_DB_PATH

        await init_db(TEST_DB_PATH)

        self.mock_bot = MagicMock()
        self.mock_bot.send_message = AsyncMock()
        self.mock_scheduler = MagicMock()
        self.app = create_web_app(bot=self.mock_bot, scheduler=self.mock_scheduler)

    async def asyncTearDown(self):
        config.BOT_TOKEN = self.orig_token
        config.ADMIN_IDS = self.orig_admin_ids
        config.DB_PATH = self.orig_db_path
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def _build_request(self, method: str, path: str, headers: dict = None, json_data: dict = None, match_info: dict = None):
        """Вспомогательный метод создания мокированного запроса aiohttp с телом и заголовками."""
        hdrs = dict(headers or {})
        if json_data is not None:
            protocol = MagicMock()
            payload = streams.StreamReader(protocol, limit=2**16, loop=asyncio.get_running_loop())
            body_bytes = json.dumps(json_data).encode("utf-8")
            payload.feed_data(body_bytes)
            payload.feed_eof()
            hdrs["Content-Type"] = "application/json"
            req = make_mocked_request(
                method,
                path,
                headers=hdrs,
                payload=payload,
                app=self.app,
                match_info=match_info or {},
            )
        else:
            req = make_mocked_request(
                method,
                path,
                headers=hdrs,
                app=self.app,
                match_info=match_info or {},
            )
        return req

    async def test_health_check(self):
        """Проверка эндпоинта /api/health."""
        req = self._build_request("GET", "/api/health")
        resp = await handle_health(req)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.text)
        self.assertTrue(data["ok"])
        self.assertEqual(data["status"], "running")

    async def test_auth_validation_and_endpoint(self):
        """Проверка валидации Telegram initData и эндпоинта /api/me."""
        user_data = {"id": TEST_ADMIN_ID, "first_name": "Анна", "last_name": "Староста", "username": "starosta"}
        valid_init_data = generate_mock_init_data(user_data, TEST_BOT_TOKEN)

        # Прямая криптографическая валидация
        res = validate_telegram_init_data(valid_init_data, TEST_BOT_TOKEN)
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], TEST_ADMIN_ID)

        # Невалидный токен
        invalid_res = validate_telegram_init_data(valid_init_data, "INVALID_TOKEN")
        self.assertIsNone(invalid_res)

        # Проверка эндпоинта /api/me через заголовок Authorization
        req = self._build_request("GET", "/api/me", headers={"Authorization": f"tma {valid_init_data}"})
        resp = await handle_auth_me(req)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.text)
        self.assertTrue(data["ok"])
        self.assertTrue(data["is_admin"])
        self.assertEqual(data["user"]["telegram_id"], TEST_ADMIN_ID)

    async def test_subjects_endpoint(self):
        """Проверка получения списка предметов."""
        req = self._build_request("GET", "/api/subjects")
        resp = await handle_get_subjects(req)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.text)
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["subjects"]), 10)
        self.assertEqual(data["subjects"][0]["name"], "Психология эмоций и мотивации")

    async def test_schedule_flow(self):
        """Проверка чтения и редактирования расписания."""
        # Чтение пустого расписания
        req_get = self._build_request("GET", "/api/schedule?week_type=current")
        resp_get = await handle_get_schedule(req_get)
        self.assertEqual(resp_get.status, 200)
        data = json.loads(resp_get.text)
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["days"]), 6)
        self.assertEqual(data["days"][0]["day_name"], "Понедельник")

        # Редактирование старостой (день 1 - Понедельник)
        update_payload = {
            "week_type": "current",
            "day_of_week": 1,
            "content": "1. Психодиагностика (ауд. 402)\n2. Статистика (ауд. 301)",
        }
        req_post = self._build_request(
            "POST",
            "/api/schedule",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            json_data=update_payload,
        )
        resp_post = await handle_update_schedule_day(req_post)
        self.assertEqual(resp_post.status, 200)

        # Повторное чтение
        resp_get2 = await handle_get_schedule(req_get)
        data2 = json.loads(resp_get2.text)
        self.assertIn("Психодиагностика", data2["days"][0]["content"])

    async def test_homework_crud(self):
        """Проверка создания, чтения, редактирования и удаления ДЗ."""
        # 1. Создание ДЗ старостой
        hw_payload = {
            "subject_id": 1,
            "due_date": "К 20 ноября",
            "task_text": "Прочитать главу 3 по мотивации",
        }
        req_create = self._build_request(
            "POST",
            "/api/homework",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            json_data=hw_payload,
        )
        resp_create = await handle_create_homework(req_create)
        self.assertEqual(resp_create.status, 200)
        hw_id = json.loads(resp_create.text)["id"]

        # 2. Получение списка
        req_list = self._build_request("GET", "/api/homework?subject_id=1")
        resp_list = await handle_get_homework(req_list)
        data_list = json.loads(resp_list.text)
        self.assertEqual(len(data_list["homework"]), 1)
        self.assertEqual(data_list["homework"][0]["task_text"], "Прочитать главу 3 по мотивации")

        # 3. Обновление ДЗ
        req_update = self._build_request(
            "PUT",
            f"/api/homework/{hw_id}",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            json_data={"due_date": "К 22 ноября", "task_text": "Прочитать главы 3 и 4"},
            match_info={"id": str(hw_id)},
        )
        resp_update = await handle_update_homework(req_update)
        self.assertEqual(resp_update.status, 200)

        # 4. Удаление ДЗ
        req_del = self._build_request(
            "DELETE",
            f"/api/homework/{hw_id}",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            match_info={"id": str(hw_id)},
        )
        resp_del = await handle_delete_homework(req_del)
        self.assertEqual(resp_del.status, 200)

        # 5. Проверка, что список пуст
        resp_list2 = await handle_get_homework(req_list)
        data_list2 = json.loads(resp_list2.text)
        self.assertEqual(len(data_list2["homework"]), 0)

    async def test_homework_manual_subject_creation(self):
        """Проверка добавления ДЗ с ручным вводом новой дисциплины."""
        payload = {
            "subject_name": "Нейропсихология",
            "due_date": "К 30 ноября",
            "task_text": "Изучить синдромы поражения лобных долей по Лурии",
        }
        req = self._build_request(
            "POST",
            "/api/homework",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            json_data=payload,
        )
        resp = await handle_create_homework(req)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.text)
        self.assertTrue(data["ok"])
        self.assertIn("subject_id", data)

        # Проверяем, что предмет появился в общем списке
        req_subjs = self._build_request("GET", "/api/subjects")
        resp_subjs = await handle_get_subjects(req_subjs)
        data_subjs = json.loads(resp_subjs.text)
        subj_names = [s["name"] for s in data_subjs["subjects"]]
        self.assertIn("Нейропсихология", subj_names)

        # Проверяем, что ДЗ доступно по новому предмету
        req_hw = self._build_request("GET", f"/api/homework?subject_id={data['subject_id']}")
        resp_hw = await handle_get_homework(req_hw)
        data_hw = json.loads(resp_hw.text)
        self.assertEqual(len(data_hw["homework"]), 1)
        self.assertEqual(data_hw["homework"][0]["subject_name"], "Нейропсихология")

    async def test_reports_flow_claim_and_unclaim(self):
        """Проверка создания пула докладов, занятия темы и отказа от темы."""
        # 1. Староста создает пул докладов
        batch_payload = {
            "subject_id": 2,
            "seminar_date": "15 декабря",
            "release_date": "10.12.2026",
            "topics": [
                "Теория черт личности Гордона Олпорта",
                "Концепция самоактуализации Маслоу",
            ],
        }
        req_create = self._build_request(
            "POST",
            "/api/reports/batches",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            json_data=batch_payload,
        )
        resp_create = await handle_create_reports_batch(req_create)
        self.assertEqual(resp_create.status, 200)
        create_data = json.loads(resp_create.text)
        batch_id = create_data["batch_id"]
        self.assertIsNone(create_data.get("release_datetime_random"))
        self.assertIn("засекречен", create_data.get("message", ""))

        # Проверяем, что в списке для старосты до публикации точное время также скрыто
        req_admin_get = self._build_request(
            "GET",
            "/api/reports/batches?subject_id=2",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
        )
        resp_admin_get = await handle_get_reports_batches(req_admin_get)
        batches_pending = json.loads(resp_admin_get.text)["batches"]
        self.assertEqual(len(batches_pending), 1)
        self.assertIsNone(batches_pending[0]["release_datetime_random"])

        # 2. Досрочная публикация старостой
        req_pub = self._build_request(
            "POST",
            f"/api/reports/batches/{batch_id}/publish",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            match_info={"id": str(batch_id)},
        )
        resp_pub = await handle_publish_reports_batch(req_pub)
        self.assertEqual(resp_pub.status, 200)

        # 3. Студент просматривает темы
        req_get = self._build_request(
            "GET",
            "/api/reports/batches?subject_id=2",
            headers={"X-Dev-Telegram-Id": str(TEST_STUDENT_ID)},
        )
        resp_get = await handle_get_reports_batches(req_get)
        self.assertEqual(resp_get.status, 200)
        batches_data = json.loads(resp_get.text)["batches"]
        self.assertEqual(len(batches_data), 1)
        topics = batches_data[0]["topics"]
        self.assertEqual(len(topics), 2)
        topic_1_id = topics[0]["id"]
        self.assertFalse(topics[0]["is_taken"])

        # 4. Студент занимает тему 1
        req_claim = self._build_request(
            "POST",
            f"/api/reports/topics/{topic_1_id}/claim",
            headers={"X-Dev-Telegram-Id": str(TEST_STUDENT_ID)},
            match_info={"id": str(topic_1_id)},
        )
        resp_claim = await handle_claim_topic(req_claim)
        self.assertEqual(resp_claim.status, 200)

        # 5. Другой студент пытается занять ту же тему -> 409 Conflict
        req_collision = self._build_request(
            "POST",
            f"/api/reports/topics/{topic_1_id}/claim",
            headers={"X-Dev-Telegram-Id": "777888"},
            match_info={"id": str(topic_1_id)},
        )
        resp_collision = await handle_claim_topic(req_collision)
        self.assertEqual(resp_collision.status, 409)

        # 6. Студент отказывается от темы
        req_unclaim = self._build_request(
            "POST",
            f"/api/reports/topics/{topic_1_id}/unclaim",
            headers={"X-Dev-Telegram-Id": str(TEST_STUDENT_ID)},
            match_info={"id": str(topic_1_id)},
        )
        resp_unclaim = await handle_unclaim_topic(req_unclaim)
        self.assertEqual(resp_unclaim.status, 200)

        # 7. Староста удаляет пул
        req_del = self._build_request(
            "DELETE",
            f"/api/reports/batches/{batch_id}",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            match_info={"id": str(batch_id)},
        )
        resp_del = await handle_delete_reports_batch(req_del)
        self.assertEqual(resp_del.status, 200)

    async def test_subjects_create_and_delete_api(self):
        """Проверка API создания и удаления предметов для честного дропа."""
        # 1. Студент не может создать предмет -> 403
        req_forbidden = self._build_request(
            "POST",
            "/api/subjects",
            headers={"X-Dev-Telegram-Id": str(TEST_STUDENT_ID)},
            json_data={"name": "Новый предмет"},
        )
        with self.assertRaises(web.HTTPForbidden):
            await handle_create_subject(req_forbidden)

        # 2. Староста создает предмет
        req_create = self._build_request(
            "POST",
            "/api/subjects",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            json_data={"name": "Психогенетика"},
        )
        resp_create = await handle_create_subject(req_create)
        self.assertEqual(resp_create.status, 200)
        data_create = json.loads(resp_create.text)
        created_id = data_create["subject"]["id"]
        self.assertEqual(data_create["subject"]["name"], "Психогенетика")

        # 3. Проверяем получение списка предметов
        req_get = self._build_request("GET", "/api/subjects")
        resp_get = await handle_get_subjects(req_get)
        self.assertEqual(resp_get.status, 200)
        subjects = json.loads(resp_get.text)["subjects"]
        self.assertIn("Психогенетика", [s["name"] for s in subjects])

        # 4. Создаем батч докладов, указав subject_name на лету
        req_batch = self._build_request(
            "POST",
            "/api/reports/batches",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            json_data={
                "subject_name": "Зоопсихология",
                "seminar_date": "25.12.2026",
                "release_date": "24.12.2026",
                "topics": ["Поведение приматов", "Условные рефлексы"],
            },
        )
        resp_batch = await handle_create_reports_batch(req_batch)
        self.assertEqual(resp_batch.status, 200)

        # Проверяем, что предмет «Зоопсихология» был автоматически создан
        req_subjs = self._build_request("GET", "/api/subjects")
        resp_subjs = await handle_get_subjects(req_subjs)
        all_subjs = json.loads(resp_subjs.text)["subjects"]
        zoo_subj = next((s for s in all_subjs if s["name"] == "Зоопсихология"), None)
        self.assertIsNotNone(zoo_subj)
        zoo_subj_id = zoo_subj["id"]

        # 5. Попытка удалить предмет, к которому привязан батч -> 400
        req_del_fail = self._build_request(
            "DELETE",
            f"/api/subjects/{zoo_subj_id}",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            match_info={"id": str(zoo_subj_id)},
        )
        resp_del_fail = await handle_delete_subject(req_del_fail)
        self.assertEqual(resp_del_fail.status, 400)

        # 6. Удаление предмета без привязок (Психогенетика) -> 200
        req_del_ok = self._build_request(
            "DELETE",
            f"/api/subjects/{created_id}",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            match_info={"id": str(created_id)},
        )
        resp_del_ok = await handle_delete_subject(req_del_ok)
        self.assertEqual(resp_del_ok.status, 200)

        # 7. Студент не может удалять предмет -> 403
        req_del_forbidden = self._build_request(
            "DELETE",
            f"/api/subjects/{zoo_subj_id}",
            headers={"X-Dev-Telegram-Id": str(TEST_STUDENT_ID)},
            match_info={"id": str(zoo_subj_id)},
        )
        with self.assertRaises(web.HTTPForbidden):
            await handle_delete_subject(req_del_forbidden)

    async def test_static_files_served(self):
        """Проверка раздачи фронтенд файлов Telegram Mini App (index.html, style.css, app.js)."""
        # Проверяем index.html
        req_index = self._build_request("GET", "/")
        match_info = await self.app.router.resolve(req_index)
        resp_index = await match_info.handler(req_index)
        self.assertEqual(resp_index.status, 200)

        # Проверяем style.css
        req_css = self._build_request("GET", "/style.css")
        match_css = await self.app.router.resolve(req_css)
        resp_css = await match_css.handler(req_css)
        self.assertEqual(resp_css.status, 200)

        # Проверяем app.js
        req_js = self._build_request("GET", "/app.js")
        match_js = await self.app.router.resolve(req_js)
        resp_js = await match_js.handler(req_js)
        self.assertEqual(resp_js.status, 200)

    async def test_reports_group_api(self):
        """Проверка API создания группового доклада и сохранения участников группы."""
        # 1. Создание группового пула
        req_create = self._build_request(
            "POST",
            "/api/reports/batches",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            json_data={
                "subject_id": 1,
                "seminar_date": "30.11.2026",
                "release_date": "29.11.2026",
                "report_type": "group",
                "topics": ["Кейс по мотивации в команде"],
            },
        )
        resp_create = await handle_create_reports_batch(req_create)
        self.assertEqual(resp_create.status, 200)
        batch_id = json.loads(resp_create.text)["batch_id"]

        # 2. Публикация
        req_pub = self._build_request(
            "POST",
            f"/api/reports/batches/{batch_id}/publish",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            match_info={"id": str(batch_id)},
        )
        resp_pub = await handle_publish_reports_batch(req_pub)
        self.assertEqual(resp_pub.status, 200)

        # 3. Проверка типа доклада в GET /api/reports/batches
        req_get = self._build_request(
            "GET",
            "/api/reports/batches?subject_id=1",
            headers={"X-Dev-Telegram-Id": str(TEST_STUDENT_ID)},
        )
        resp_get = await handle_get_reports_batches(req_get)
        self.assertEqual(resp_get.status, 200)
        batches = json.loads(resp_get.text)["batches"]
        cur_batch = next((b for b in batches if b["id"] == batch_id), None)
        self.assertIsNotNone(cur_batch)
        self.assertEqual(cur_batch["report_type"], "group")
        topic = cur_batch["topics"][0]
        topic_id = topic["id"]

        # 4. Запись на групповой доклад с указанием участников
        members = "Студент Тестовый, Анна Смирнова, Дмитрий Волков"
        req_claim = self._build_request(
            "POST",
            f"/api/reports/topics/{topic_id}/claim",
            headers={"X-Dev-Telegram-Id": str(TEST_STUDENT_ID)},
            match_info={"id": str(topic_id)},
            json_data={"group_members": members},
        )
        resp_claim = await handle_claim_topic(req_claim)
        self.assertEqual(resp_claim.status, 200)

        # 5. Проверка сохранения списка участников в ответе GET
        resp_get2 = await handle_get_reports_batches(req_get)
        batches2 = json.loads(resp_get2.text)["batches"]
        cur_batch2 = next((b for b in batches2 if b["id"] == batch_id), None)
        self.assertEqual(cur_batch2["topics"][0]["group_members"], members)
        self.assertTrue(cur_batch2["topics"][0]["is_taken"])

        # 6. Отказ от темы очищает участников
        req_unclaim = self._build_request(
            "POST",
            f"/api/reports/topics/{topic_id}/unclaim",
            headers={"X-Dev-Telegram-Id": str(TEST_STUDENT_ID)},
            match_info={"id": str(topic_id)},
        )
        resp_unclaim = await handle_unclaim_topic(req_unclaim)
        self.assertEqual(resp_unclaim.status, 200)

        resp_get3 = await handle_get_reports_batches(req_get)
        batches3 = json.loads(resp_get3.text)["batches"]
        cur_batch3 = next((b for b in batches3 if b["id"] == batch_id), None)
        self.assertIsNone(cur_batch3["topics"][0]["group_members"])
        self.assertFalse(cur_batch3["topics"][0]["is_taken"])

    async def test_spin_random_api(self):
        """Проверка API ручного визуального рандомайзера и отправки уведомления."""
        # 1. Создаем пул с 2 темами
        req_create = self._build_request(
            "POST",
            "/api/reports/batches",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            json_data={
                "subject_id": 1,
                "seminar_date": "12.12.2026",
                "release_date": "10.12.2026",
                "topics": ["Тема рандома 1", "Тема рандома 2"],
            },
        )
        resp_create = await handle_create_reports_batch(req_create)
        self.assertEqual(resp_create.status, 200)
        batch_id = json.loads(resp_create.text)["batch_id"]

        # Получаем созданные темы
        req_get = self._build_request(
            "GET",
            f"/api/reports/batches?subject_id=1",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
        )
        resp_get = await handle_get_reports_batches(req_get)
        batches = json.loads(resp_get.text)["batches"]
        cur_batch = next((b for b in batches if b["id"] == batch_id), None)
        topic_1_id = cur_batch["topics"][0]["id"]

        # 2. Не-администратор не имеет права крутить рулетку -> 403
        req_spin_forbidden = self._build_request(
            "POST",
            f"/api/reports/topics/{topic_1_id}/spin-random",
            headers={"X-Dev-Telegram-Id": str(TEST_STUDENT_ID)},
            match_info={"id": str(topic_1_id)},
        )
        with self.assertRaises(web.HTTPForbidden):
            await handle_spin_random_topic(req_spin_forbidden)

        # 3. Мокируем бота для проверки отправки уведомления студенту
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        self.app[BOT_KEY] = mock_bot

        # 4. Староста запускает рандомайзер
        req_spin_ok = self._build_request(
            "POST",
            f"/api/reports/topics/{topic_1_id}/spin-random",
            headers={"X-Dev-Telegram-Id": str(TEST_ADMIN_ID)},
            match_info={"id": str(topic_1_id)},
        )
        resp_spin = await handle_spin_random_topic(req_spin_ok)
        self.assertEqual(resp_spin.status, 200)
        spin_result = json.loads(resp_spin.text)
        self.assertTrue(spin_result["ok"])
        self.assertIn("winner", spin_result)
        self.assertIn("candidates", spin_result)
        self.assertEqual(spin_result["topic"]["id"], topic_1_id)

        # 5. Проверяем, что бот отправил уведомление выпавшему студенту
        mock_bot.send_message.assert_called_once()
        sent_call_args = mock_bot.send_message.call_args[1]
        self.assertEqual(sent_call_args["chat_id"], spin_result["winner"]["telegram_id"])
        self.assertIn("Вам случайным образом выпал доклад", sent_call_args["text"])
        self.assertIn("Тема рандома 1", sent_call_args["text"])

        # 6. Повторный запуск для уже занятой темы возвращает 400
        resp_spin_again = await handle_spin_random_topic(req_spin_ok)
        self.assertEqual(resp_spin_again.status, 400)

    async def test_homework_file_attachment_and_download_api(self):
        """Проверка отдачи метаданных файла в /api/homework и скачивания через /api/homework/{id}/download."""
        import tempfile
        from bot.database import add_homework, update_homework

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "psychology_guide.pdf")
            with open(file_path, "wb") as f:
                f.write(b"%PDF-1.4 test guide content")

            # Создаем ДЗ с прикрепленным файлом
            hw_id = await add_homework(
                subject_id=1,
                due_date="12.12.2026",
                task_text="Прочитать главу 3",
                db_path=TEST_DB_PATH,
                file_path=file_path,
                file_name="psychology_guide.pdf",
                file_size=len(b"%PDF-1.4 test guide content"),
            )

            # 1. Запрос списка ДЗ
            req_list = self._build_request("GET", "/api/homework")
            resp_list = await handle_get_homework(req_list)
            self.assertEqual(resp_list.status, 200)
            data_list = json.loads(resp_list.text)
            self.assertTrue(data_list["ok"])
            hw_item = next(h for h in data_list["homework"] if h["id"] == hw_id)
            self.assertEqual(hw_item["file_name"], "psychology_guide.pdf")
            self.assertTrue(hw_item["has_file"])
            self.assertFalse(hw_item["is_file_expired"])
            self.assertEqual(hw_item["download_url"], f"/api/homework/{hw_id}/download")
            self.assertNotIn("file_path", hw_item)

            # 2. Скачивание активного файла
            req_dl = self._build_request(
                "GET",
                f"/api/homework/{hw_id}/download",
                match_info={"id": str(hw_id)},
            )
            resp_dl = await handle_download_homework_file(req_dl)
            self.assertEqual(resp_dl.status, 200)
            self.assertIn("attachment", resp_dl.headers.get("Content-Disposition", ""))

            # 3. Обновляем статус на просроченный файл
            await update_homework(
                hw_id,
                file_path=None,
                file_name="[Срок хранения файла истек]",
                db_path=TEST_DB_PATH,
            )
            resp_expired_dl = await handle_download_homework_file(req_dl)
            self.assertEqual(resp_expired_dl.status, 410)
            data_exp = json.loads(resp_expired_dl.text)
            self.assertFalse(data_exp["ok"])
            self.assertIn("истек", data_exp["error"])


if __name__ == "__main__":
    unittest.main()
