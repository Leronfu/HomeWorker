"""Обработчики REST API для Telegram Mini App (Web App)."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from aiohttp import web

from bot import config
from bot.database import (
    DEFAULT_SUBJECTS,
    add_homework,
    add_or_update_user,
    claim_topic,
    clear_week_schedule,
    copy_next_to_current_week,
    create_report_batch,
    delete_homework,
    delete_report_batch,
    get_all_homework,
    get_all_report_batches,
    get_all_subjects,
    get_or_create_subject,
    get_batch_by_id,
    get_batch_topics,
    get_homework_by_id,
    get_homework_by_subject,
    get_schedule,
    get_user,
    publish_report_batch,
    unclaim_topic,
    update_homework,
    update_schedule_day,
)
from bot.utils.scheduler import broadcast_report_drop
from bot.utils.report_helpers import generate_random_release_datetime
from bot.web.auth import validate_telegram_init_data

logger = logging.getLogger(__name__)

DAY_NAMES = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
}


def json_response(data: Any, status: int = 200) -> web.Response:
    """Вспомогательная функция для генерации JSON-ответа с заголовками CORS."""
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Telegram-Init-Data, X-Dev-Telegram-Id",
    }
    return web.Response(
        text=json.dumps(data, ensure_ascii=False, default=str),
        status=status,
        content_type="application/json",
        charset="utf-8",
        headers=headers,
    )


async def options_handler(request: web.Request) -> web.Response:
    """Pre-flight CORS handler."""
    return json_response({"ok": True})


async def authenticate_request(request: web.Request) -> Optional[Dict[str, Any]]:
    """
    Извлечение и аутентификация пользователя из Telegram Web App initData.
    
    Поддерживает:
    - Заголовок Authorization: tma <initData>
    - Заголовок X-Telegram-Init-Data: <initData>
    - Query-параметр ?initData=...
    - В dev-режиме: заголовок X-Dev-Telegram-Id / query ?dev_telegram_id=...
    """
    bot_token = config.BOT_TOKEN

    # 1. Проверяем Dev-режим для локального тестирования
    dev_id = request.headers.get("X-Dev-Telegram-Id") or request.query.get("dev_telegram_id")
    if dev_id and dev_id.isdigit():
        tg_id = int(dev_id)
        user = await get_user(tg_id)
        is_adm = config.is_admin(tg_id)
        if not user:
            name = "Староста (Тест)" if is_adm else f"Студент {tg_id}"
            await add_or_update_user(tg_id, f"test_{tg_id}", name, is_adm)
            user = await get_user(tg_id)
        user_dict = dict(user) if user else {"telegram_id": tg_id, "full_name": f"Студент {tg_id}"}
        user_dict["is_admin"] = is_adm
        return user_dict

    # 2. Извлекаем initData
    init_data = ""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("tma "):
        init_data = auth_header[4:].strip()
    elif "X-Telegram-Init-Data" in request.headers:
        init_data = request.headers["X-Telegram-Init-Data"].strip()
    elif "initData" in request.query:
        init_data = request.query["initData"].strip()

    if not init_data:
        return None

    # Валидация подписи Telegram
    tg_user = validate_telegram_init_data(init_data, bot_token)
    if not tg_user or "id" not in tg_user:
        return None

    tg_id = int(tg_user["id"])
    username = tg_user.get("username", "")
    first_name = tg_user.get("first_name", "")
    last_name = tg_user.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip() or username or f"Студент {tg_id}"
    is_adm = config.is_admin(tg_id)

    # Синхронизируем пользователя в SQLite
    db_user = await get_user(tg_id)
    if not db_user:
        await add_or_update_user(tg_id, username, full_name, is_adm)
        db_user = await get_user(tg_id)
    else:
        # Обновим имя, если оно было пустым
        if not db_user.get("full_name"):
            await add_or_update_user(tg_id, username, full_name, is_adm)
            db_user = await get_user(tg_id)

    user_dict = dict(db_user) if db_user else {"telegram_id": tg_id, "full_name": full_name}
    user_dict["is_admin"] = is_adm
    return user_dict


async def require_auth(request: web.Request) -> Dict[str, Any]:
    """Требовать аутентифицированного пользователя."""
    user = await authenticate_request(request)
    if not user:
        raise web.HTTPUnauthorized(
            text=json.dumps({"ok": False, "error": "Необходима авторизация через Telegram Mini App"}),
            content_type="application/json",
        )
    return user


async def require_admin(request: web.Request) -> Dict[str, Any]:
    """Требовать права администратора (старосты)."""
    user = await require_auth(request)
    if not user.get("is_admin"):
        raise web.HTTPForbidden(
            text=json.dumps({"ok": False, "error": "Доступ разрешен только старосте группы"}),
            content_type="application/json",
        )
    return user


# ---------------- API HANDLERS ---------------- #

async def handle_health(request: web.Request) -> web.Response:
    """Проверка жизнеспособности сервера."""
    return json_response({"ok": True, "service": "HomeWorker Mini App", "status": "running"})


async def handle_auth_me(request: web.Request) -> web.Response:
    """Получение профиля текущего пользователя и его роли."""
    user = await require_auth(request)
    return json_response({"ok": True, "user": user, "is_admin": user.get("is_admin", False)})


async def handle_get_subjects(request: web.Request) -> web.Response:
    """Получение списка всех предметов."""
    subjects = await get_all_subjects()
    return json_response({"ok": True, "subjects": subjects})


async def handle_get_schedule(request: web.Request) -> web.Response:
    """Получение расписания на текущую или следующую неделю."""
    week_type = request.query.get("week_type", "current")
    if week_type not in ("current", "next"):
        return json_response({"ok": False, "error": "Параметр week_type должен быть 'current' или 'next'"}, 400)

    rows = await get_schedule(week_type)
    days = []
    # Дни с 1 по 6 (Пн - Сб)
    day_map = {row["day_of_week"]: row["content"] for row in rows}
    for day_idx in range(1, 7):
        days.append({
            "day_of_week": day_idx,
            "day_name": DAY_NAMES[day_idx],
            "content": day_map.get(day_idx, ""),
        })

    return json_response({"ok": True, "week_type": week_type, "days": days})


async def handle_update_schedule_day(request: web.Request) -> web.Response:
    """Обновление текста расписания для конкретного дня (только староста)."""
    await require_admin(request)
    try:
        data = await request.json()
    except Exception:
        return json_response({"ok": False, "error": "Неверный формат JSON"}, 400)

    week_type = data.get("week_type")
    day_of_week = data.get("day_of_week")
    content = data.get("content", "").strip()

    if week_type not in ("current", "next") or not isinstance(day_of_week, int) or not (1 <= day_of_week <= 6):
        return json_response({"ok": False, "error": "Некорректный день (от 1 до 6) или тип недели"}, 400)

    await update_schedule_day(week_type, day_of_week, content)
    return json_response({"ok": True, "message": "Расписание успешно обновлено"})


async def handle_rollover_schedule(request: web.Request) -> web.Response:
    """Принудительный перенос расписания со следующей недели на текущую (только староста)."""
    await require_admin(request)
    await copy_next_to_current_week()
    return json_response({"ok": True, "message": "Расписание перенесено на текущую неделю"})


async def handle_clear_schedule(request: web.Request) -> web.Response:
    """Очистка расписания недели (только староста)."""
    await require_admin(request)
    try:
        data = await request.json()
    except Exception:
        return json_response({"ok": False, "error": "Неверный формат JSON"}, 400)

    week_type = data.get("week_type")
    if week_type not in ("current", "next"):
        return json_response({"ok": False, "error": "Некорректный тип недели"}, 400)

    await clear_week_schedule(week_type)
    return json_response({"ok": True, "message": f"Расписание недели '{week_type}' очищено"})


async def handle_get_homework(request: web.Request) -> web.Response:
    """Получение домашних заданий (по предмету или всех)."""
    subject_id_raw = request.query.get("subject_id")
    if subject_id_raw and subject_id_raw.isdigit():
        items = await get_homework_by_subject(int(subject_id_raw))
    else:
        items = await get_all_homework()
    return json_response({"ok": True, "homework": items})


async def handle_create_homework(request: web.Request) -> web.Response:
    """Добавление домашнего задания (только староста)."""
    await require_admin(request)
    try:
        data = await request.json()
    except Exception:
        return json_response({"ok": False, "error": "Неверный формат JSON"}, 400)

    subject_id = data.get("subject_id")
    subject_name = str(data.get("subject_name", "")).strip()
    due_date = str(data.get("due_date", "")).strip()
    task_text = str(data.get("task_text", "")).strip()

    if not due_date or not task_text:
        return json_response({"ok": False, "error": "Необходимо указать due_date и task_text"}, 400)

    # Если передано текстовое название предмета вручную
    if subject_name:
        subj = await get_or_create_subject(subject_name)
        final_subject_id = subj["id"]
    elif subject_id and str(subject_id).isdigit() and int(subject_id) > 0:
        final_subject_id = int(subject_id)
    else:
        return json_response({"ok": False, "error": "Необходимо выбрать предмет или ввести его название вручную"}, 400)

    hw_id = await add_homework(final_subject_id, due_date, task_text)
    return json_response({
        "ok": True,
        "id": hw_id,
        "subject_id": final_subject_id,
        "message": "Домашнее задание добавлено"
    })


async def handle_update_homework(request: web.Request) -> web.Response:
    """Редактирование домашнего задания (только староста)."""
    await require_admin(request)
    hw_id = int(request.match_info["id"])
    try:
        data = await request.json()
    except Exception:
        return json_response({"ok": False, "error": "Неверный формат JSON"}, 400)

    due_date = data.get("due_date")
    task_text = data.get("task_text")

    updated = await update_homework(hw_id, due_date=due_date, task_text=task_text)
    if not updated:
        return json_response({"ok": False, "error": "Задание не найдено или не изменено"}, 404)
    return json_response({"ok": True, "message": "Задание обновлено"})


async def handle_delete_homework(request: web.Request) -> web.Response:
    """Удаление домашнего задания (только староста)."""
    await require_admin(request)
    hw_id = int(request.match_info["id"])
    deleted = await delete_homework(hw_id)
    if not deleted:
        return json_response({"ok": False, "error": "Задание не найдено"}, 404)
    return json_response({"ok": True, "message": "Задание удалено"})


async def handle_get_reports_batches(request: web.Request) -> web.Response:
    """Получение пулов докладов и тем."""
    user = await require_auth(request)
    is_adm = user.get("is_admin", False)
    subject_id_raw = request.query.get("subject_id")
    subject_id = int(subject_id_raw) if (subject_id_raw and subject_id_raw.isdigit()) else None

    all_batches = await get_all_report_batches()
    result = []

    for b in all_batches:
        # Студенты видят только опубликованные доклады
        if not is_adm and not b["is_published"]:
            continue
        if subject_id and b["subject_id"] != subject_id:
            continue

        topics = await get_batch_topics(b["id"])
        topics_formatted = []
        for t in topics:
            topics_formatted.append({
                "id": t["id"],
                "topic_number": t["topic_number"],
                "topic_text": t["topic_text"],
                "user_id": t["user_id"],
                "student_name": t.get("student_name") or (t.get("student_username") and f"@{t['student_username']}"),
                "is_taken": bool(t["user_id"]),
                "is_mine": bool(t["user_id"] and t["user_id"] == user["telegram_id"]),
            })

        batch_dict = dict(b)
        # Скрываем точное случайное время дропа даже от старосты/админа, пока партия не опубликована
        if not b.get("is_published"):
            batch_dict["release_datetime_random"] = None
        batch_dict["topics"] = topics_formatted
        result.append(batch_dict)

    return json_response({"ok": True, "batches": result})


def _get_bot(app: web.Application) -> Optional[Any]:
    from bot.web.server import BOT_KEY
    return app.get(BOT_KEY)


def _get_scheduler(app: web.Application) -> Optional[Any]:
    from bot.web.server import SCHEDULER_KEY
    return app.get(SCHEDULER_KEY)


async def handle_create_reports_batch(request: web.Request) -> web.Response:
    """Создание нового пула докладов со случайным временем дропа (только староста)."""
    await require_admin(request)
    try:
        data = await request.json()
    except Exception:
        return json_response({"ok": False, "error": "Неверный формат JSON"}, 400)

    subject_id = data.get("subject_id")
    seminar_date = str(data.get("seminar_date", "")).strip()
    release_date_str = str(data.get("release_date", "")).strip()
    topics_raw = data.get("topics")

    if not subject_id or not seminar_date or not release_date_str or not topics_raw:
        return json_response({"ok": False, "error": "Заполните все поля: предмет, дату семинара, дату дропа и темы"}, 400)

    # Нормализуем список тем
    if isinstance(topics_raw, list):
        topics_list = [str(t).strip() for t in topics_raw if str(t).strip()]
    elif isinstance(topics_raw, str):
        topics_list = [t.strip() for t in topics_raw.split("\n") if t.strip()]
    else:
        topics_list = []

    if not topics_list:
        return json_response({"ok": False, "error": "Список тем не может быть пустым"}, 400)

    # Парсим дату дропа и генерируем случайное время
    try:
        for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                drop_d = datetime.strptime(release_date_str, fmt).date()
                break
            except ValueError:
                continue
        else:
            return json_response({"ok": False, "error": "Неверный формат даты дропа. Используйте ДД.ММ.ГГГГ"}, 400)
    except Exception:
        return json_response({"ok": False, "error": "Ошибка валидации даты дропа"}, 400)

    random_release_dt = generate_random_release_datetime(drop_d)
    random_release_str = random_release_dt.strftime("%Y-%m-%d %H:%M:%S")

    batch_id = await create_report_batch(
        subject_id=int(subject_id),
        seminar_date=seminar_date,
        release_date=drop_d.strftime("%Y-%m-%d"),
        release_datetime_random=random_release_str,
        topics=topics_list,
    )

    # Ставим задачу в планировщик, если он доступен
    scheduler = _get_scheduler(request.app)
    bot = _get_bot(request.app)
    now_msk = datetime.now(ZoneInfo("Europe/Moscow"))

    if scheduler and bot:
        job_id = f"report_drop_{batch_id}"
        if random_release_dt > now_msk:
            scheduler.add_job(
                broadcast_report_drop,
                trigger="date",
                run_date=random_release_dt,
                args=[bot, batch_id],
                id=job_id,
                replace_existing=True,
            )
            logger.info("Запланирован дроп докладов #%s на %s", batch_id, random_release_str)
        else:
            # Если время уже наступило, публикуем немедленно
            await publish_report_batch(batch_id)
            scheduler.add_job(broadcast_report_drop, args=[bot, batch_id])

    return json_response({
        "ok": True,
        "batch_id": batch_id,
        "release_datetime_random": None,
        "message": f"Пул докладов создан! Темы будут опубликованы в случайное засекреченное время ({drop_d.strftime('%d.%m.%Y')})",
    })


async def handle_delete_reports_batch(request: web.Request) -> web.Response:
    """Удаление пула докладов (только староста)."""
    await require_admin(request)
    batch_id = int(request.match_info["id"])

    scheduler = _get_scheduler(request.app)
    if scheduler:
        job_id = f"report_drop_{batch_id}"
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass

    deleted = await delete_report_batch(batch_id)
    if not deleted:
        return json_response({"ok": False, "error": "Пул докладов не найден"}, 404)
    return json_response({"ok": True, "message": "Пул докладов удален"})


async def handle_publish_reports_batch(request: web.Request) -> web.Response:
    """Принудительная немедленная публикация докладов старостой."""
    await require_admin(request)
    batch_id = int(request.match_info["id"])

    scheduler = _get_scheduler(request.app)
    bot = _get_bot(request.app)

    if scheduler:
        job_id = f"report_drop_{batch_id}"
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass

    await publish_report_batch(batch_id)
    if bot:
        await broadcast_report_drop(bot, batch_id)

    return json_response({"ok": True, "message": "Доклады успешно опубликованы и разосланы группе!"})


async def handle_claim_topic(request: web.Request) -> web.Response:
    """Запись студента на свободную тему доклада (атомарная операция)."""
    user = await require_auth(request)
    topic_id = int(request.match_info["id"])

    claimed = await claim_topic(topic_id, user["telegram_id"])
    if not claimed:
        return json_response({"ok": False, "error": "Упс! Эту тему только что занял другой студент"}, 409)

    return json_response({"ok": True, "message": "Тема успешно закреплена за вами!"})


async def handle_unclaim_topic(request: web.Request) -> web.Response:
    """Отказ от выбранной темы доклада."""
    user = await require_auth(request)
    topic_id = int(request.match_info["id"])

    unclaimed = await unclaim_topic(topic_id, user["telegram_id"])
    if not unclaimed:
        return json_response({"ok": False, "error": "Не удалось отказаться от темы"}, 400)

    return json_response({"ok": True, "message": "Вы успешно отказались от темы"})
