"""Утилиты для форматирования домашних заданий."""

import html
from typing import Any, Dict, List


def format_homework_list_student(subject_name: str, homework_list: List[Dict[str, Any]]) -> str:
    """Форматирование списка домашних заданий для студента."""
    header = f"📚 <b>{html.escape(subject_name)}</b>"

    if not homework_list:
        return (
            f"{header}\n\n"
            f"🎉 <i>Актуальных домашних заданий по этому предмету пока нет! Отдыхаем!</i>"
        )

    lines: List[str] = [
        f"{header}\n",
        f"📝 <b>Всего заданий: {len(homework_list)}</b>\n",
    ]

    for idx, hw in enumerate(homework_list, start=1):
        due_date = html.escape(str(hw.get("due_date", "—")))
        task_text = html.escape(str(hw.get("task_text", "")).strip())
        file_info = ""
        f_name = hw.get("file_name")
        if f_name:
            if f_name == "[Срок хранения файла истек]":
                file_info = "\n📎 <i>[Срок хранения файла истек]</i>"
            else:
                file_info = f"\n📎 <b>Прикрепленный файл:</b> {html.escape(f_name)}"

        lines.append(
            f"📌 <b>Задание #{idx}</b> (срок: <code>{due_date}</code>)\n"
            f"{task_text}{file_info}\n"
        )

    return "\n".join(lines)


def format_homework_detail_admin(homework: Dict[str, Any]) -> str:
    """Форматирование детальной карточки задания для панели старосты."""
    subject_name = html.escape(str(homework.get("subject_name", "Предмет")))
    due_date = html.escape(str(homework.get("due_date", "—")))
    task_text = html.escape(str(homework.get("task_text", "")).strip())
    hw_id = homework.get("id")

    file_info = ""
    f_name = homework.get("file_name")
    if f_name:
        if f_name == "[Срок хранения файла истек]":
            file_info = "\n📎 <i>[Срок хранения файла истек]</i>\n"
        else:
            file_info = f"\n📎 <b>Файл:</b> {html.escape(f_name)}\n"

    return (
        f"📋 <b>Управление заданием #{hw_id}</b>\n\n"
        f"📚 <b>Предмет:</b> {subject_name}\n"
        f"📅 <b>Срок сдачи:</b> <code>{due_date}</code>\n"
        f"{file_info}\n"
        f"✍️ <b>Текст задания:</b>\n{task_text}"
    )
