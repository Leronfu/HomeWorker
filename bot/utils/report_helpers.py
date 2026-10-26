"""Вспомогательные утилиты для работы с темами докладов, парсинга дат и генерации случайного времени."""

import html
import random
import re
from datetime import date, datetime, time, timezone, timedelta
from typing import Any, Dict, List, Optional
import zoneinfo

MSK_TZ = zoneinfo.ZoneInfo("Europe/Moscow")


def parse_topics_text(raw_text: str) -> List[str]:
    """Парсинг списка тем докладов из текста сообщения.
    
    Удаляет маркеры списка (1., 1), -, *, •), обрезает пробелы и исключает пустые строки.
    """
    topics: List[str] = []
    for line in raw_text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        # Удаляем ведущую нумерацию вида "1.", "1)", "-", "•", "*"
        cleaned = re.sub(r"^(\d+[\.\)]|[-*•—])\s*", "", cleaned).strip()
        if cleaned:
            topics.append(cleaned)
    return topics


def parse_release_date(raw_date: str) -> Optional[date]:
    """Парсинг строки с датой публикации (дропа).
    
    Поддерживаемые форматы:
    - ДД.ММ.ГГГГ (например, 28.10.2026)
    - ДД.ММ (например, 28.10 — подставляется текущий или следующий год)
    - ГГГГ-ММ-ДД (например, 2026-10-28)
    """
    cleaned = raw_date.strip()
    now_msk = datetime.now(MSK_TZ).date()

    # Формат ДД.ММ.ГГГГ
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(cleaned, fmt).date()
            return parsed
        except ValueError:
            pass

    # Формат ДД.ММ
    if re.match(r"^\d{1,2}\.\d{1,2}$", cleaned):
        try:
            day, month = map(int, cleaned.split("."))
            year = now_msk.year
            parsed = date(year, month, day)
            # Если дата в этом году уже прошла, берем следующий год
            if parsed < now_msk:
                parsed = date(year + 1, month, day)
            return parsed
        except ValueError:
            return None

    return None


def generate_random_release_datetime(
    release_date: date, min_hour: int = 12, max_hour: int = 20
) -> datetime:
    """Генерация случайного времени публикации тем в указанный день.
    
    Интервал по умолчанию: строго с 12:00 до 20:00 по московскому времени (МСК),
    чтобы уведомление отправлялось строго в активное дневное время.
    """
    now_msk = datetime.now(MSK_TZ)
    min_sec = min_hour * 3600
    max_sec = max_hour * 3600

    # Если публикация назначена на сегодня
    if release_date == now_msk.date():
        now_sec = now_msk.hour * 3600 + now_msk.minute * 60 + now_msk.second
        if now_sec >= max_sec:
            # Если уже вечер текущего дня (после 20:00), ставим через 2 минуты
            return now_msk + timedelta(minutes=2)
        start_sec = max(min_sec, now_sec + 60)
        if start_sec >= max_sec:
            return now_msk + timedelta(minutes=2)
        chosen_sec = random.randint(start_sec, max_sec)
    else:
        chosen_sec = random.randint(min_sec, max_sec)

    rand_hour = chosen_sec // 3600
    rand_minute = (chosen_sec % 3600) // 60
    rand_second = chosen_sec % 60
    return datetime(
        release_date.year,
        release_date.month,
        release_date.day,
        rand_hour,
        rand_minute,
        rand_second,
        tzinfo=MSK_TZ,
    )


def format_report_batch_admin(batch: Dict[str, Any], topics: List[Dict[str, Any]]) -> str:
    """Форматирование детальной информации о партии докладов для старосты."""
    subject_name = html.escape(str(batch.get("subject_name", "Предмет")))
    seminar_date = html.escape(str(batch.get("seminar_date", "—")))
    release_date = html.escape(str(batch.get("release_date", "—")))
    release_dt_raw = batch.get("release_datetime_random", "—")
    is_published = bool(batch.get("is_published", False))

    if is_published:
        status_line = "🟢 <b>Статус: Опубликовано (темы доступны студентам)</b>"
    else:
        status_line = "⏳ <b>Статус: Запланирован дроп</b>\n⏰ <b>Время дропа:</b> <i>Случайное время засекречено (опубликуется автоматически)</i>"

    report_type = "👥 Групповой" if batch.get("report_type") == "group" else "👤 Индивидуальный"

    lines = [
        f"🎤 <b>Партия докладов #{batch['id']}</b>\n",
        f"📚 <b>Предмет:</b> {subject_name}",
        f"👥 <b>Формат:</b> {report_type}",
        f"🗓 <b>Дата семинара:</b> <code>{seminar_date}</code>",
        f"📅 <b>Дата дропа:</b> <code>{release_date}</code>",
        status_line,
        f"\n📝 <b>Список тем ({len(topics)}):</b>",
    ]

    for t in topics:
        num = t.get("topic_number", 1)
        topic_text = html.escape(str(t.get("topic_text", "")))
        student_name = t.get("student_name")
        group_members = t.get("group_members")
        if student_name:
            if group_members:
                status = f"✅ Занято (<b>{html.escape(student_name)}</b>, группа: <i>{html.escape(group_members)}</i>)"
            else:
                status = f"✅ Занято (<b>{html.escape(student_name)}</b>)"
        else:
            status = "🟢 Свободно"
        lines.append(f"{num}. {topic_text} — {status}")

    return "\n".join(lines)


def format_report_batch_student(
    batch: Dict[str, Any], topics: List[Dict[str, Any]], user_id: Optional[int] = None
) -> str:
    """Форматирование списка тем докладов для студента."""
    subject_name = html.escape(str(batch.get("subject_name", "Предмет")))
    seminar_date = html.escape(str(batch.get("seminar_date", "—")))
    report_type = "👥 Групповой" if batch.get("report_type") == "group" else "👤 Индивидуальный"

    free_count = sum(1 for t in topics if t.get("user_id") is None)
    total_count = len(topics)

    lines = [
        f"🎤 <b>Доклады: {subject_name}</b>",
        f"👥 <b>Формат:</b> {report_type}",
        f"🗓 <b>Дата семинара:</b> <code>{seminar_date}</code>",
        f"📊 <b>Свободно тем:</b> {free_count} из {total_count}\n",
        "📝 <b>Список тем:</b>",
    ]

    user_claimed_number = None

    for t in topics:
        num = t.get("topic_number", 1)
        topic_text = html.escape(str(t.get("topic_text", "")))
        topic_user_id = t.get("user_id")
        student_name = t.get("student_name")
        group_members = t.get("group_members")

        if topic_user_id is not None:
            if user_id and topic_user_id == user_id:
                user_claimed_number = num
                if group_members:
                    status = f"🌟 <b>Занято вашей группой:</b> {html.escape(group_members)}"
                else:
                    status = f"🌟 <b>Занято вами ({html.escape(student_name or 'Вы')})</b>"
            else:
                if group_members:
                    status = f"✅ Занято (<b>{html.escape(student_name or 'Студент')}</b>, группа: <i>{html.escape(group_members)}</i>)"
                else:
                    status = f"✅ Занято (<b>{html.escape(student_name or 'Студент')}</b>)"
        else:
            status = "🟢 Свободно"

        lines.append(f"{num}. {topic_text} — {status}")

    if user_claimed_number:
        lines.append(
            f"\n💡 <i>Вы заняли тему №{user_claimed_number}. "
            "Если хотите сменить её, сначала нажмите кнопку «Отказаться от темы» ниже.</i>"
        )
    elif free_count > 0:
        lines.append("\n👉 <i>Нажмите на кнопку с номером свободной темы ниже, чтобы занять её:</i>")
    else:
        lines.append("\n🔒 <i>Все темы в этой партии уже заняты одногруппниками.</i>")

    return "\n".join(lines)

