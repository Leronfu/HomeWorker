"""Утилиты для форматирования расписания и работы с днями недели."""

import html
from typing import Any, Dict, List

# Названия дней недели для университета (Пн-Сб)
WEEKDAYS: Dict[int, str] = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
}

WEEKDAY_SHORT: Dict[int, str] = {
    1: "Пн",
    2: "Вт",
    3: "Ср",
    4: "Чт",
    5: "Пт",
    6: "Сб",
}


def get_weekday_name(day: int) -> str:
    """Получить полное название дня недели."""
    return WEEKDAYS.get(day, f"День {day}")


def get_weekday_short(day: int) -> str:
    """Получить сокращенное название дня недели."""
    return WEEKDAY_SHORT.get(day, str(day))


def format_schedule_text(schedule_rows: List[Dict[str, Any]], week_type: str = "current") -> str:
    """Красиво отформатировать расписание на неделю для отправки студентам.
    
    :param schedule_rows: список записей из БД с полями day_of_week и content
    :param week_type: 'current' (текущая) или 'next' (следующая)
    :return: HTML-отформатированный текст расписания
    """
    week_title = "Текущая неделя" if week_type == "current" else "Следующая неделя"
    header = f"📅 <b>Расписание занятий ({week_title})</b>\n"

    # Создаем мапу день -> контент
    day_map: Dict[int, str] = {}
    for row in schedule_rows:
        day_map[row["day_of_week"]] = (row["content"] or "").strip()

    has_any = any(bool(day_map.get(d)) for d in range(1, 7))

    if not has_any:
        return (
            f"{header}\n"
            f"<i>Расписание на эту неделю пока не заполнено старостой.</i>"
        )

    lines: List[str] = [header]
    for day_num in range(1, 7):
        day_name = WEEKDAYS[day_num]
        content = day_map.get(day_num, "")
        if content:
            lines.append(f"\n🔹 <b>{day_name}</b>:\n{html.escape(content)}")
        else:
            lines.append(f"\n🔹 <b>{day_name}</b>:\n<i>Занятий нет</i>")

    return "\n".join(lines)


def format_day_preview(day_of_week: int, week_type: str, content: str) -> str:
    """Отформатировать карточку конкретного дня для предпросмотра админом."""
    day_name = get_weekday_name(day_of_week)
    week_title = "Текущая неделя" if week_type == "current" else "Следующая неделя"
    cleaned = (content or "").strip()
    content_display = html.escape(cleaned) if cleaned else "<i>(расписание не заполнено / пусто)</i>"

    return (
        f"🗓 <b>{day_name}</b> (<i>{week_title}</i>)\n\n"
        f"<b>Текущий текст:</b>\n{content_display}"
    )
