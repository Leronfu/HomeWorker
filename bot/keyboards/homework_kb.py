"""Клавиатуры для модуля домашних заданий (студенты и староста)."""

from typing import Any, Dict, List, Optional
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_subjects_keyboard(
    subjects: List[Dict[str, Any]],
    callback_prefix: str = "hw_subj",
    back_callback: Optional[str] = None,
    extra_buttons: Optional[List[InlineKeyboardButton]] = None,
) -> InlineKeyboardMarkup:
    """Генерация списка кнопок с предметами.
    
    :param subjects: Список словарей предметов из БД (id, name).
    :param callback_prefix: Префикс для callback_data (например, 'hw_subj' или 'ahw_add_pick').
    :param back_callback: Опциональная callback_data для кнопки '« Назад'.
    :param extra_buttons: Дополнительные кнопки (например, ввод предмета вручную).
    """
    keyboard: List[List[InlineKeyboardButton]] = []

    for subj in subjects:
        subj_id = subj["id"]
        subj_name = subj["name"]
        keyboard.append([
            InlineKeyboardButton(
                text=f"📚 {subj_name}",
                callback_data=f"{callback_prefix}:{subj_id}",
            )
        ])

    if extra_buttons:
        for btn in extra_buttons:
            keyboard.append([btn])

    if back_callback:
        keyboard.append([
            InlineKeyboardButton(
                text="« Назад",
                callback_data=back_callback,
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_student_homework_keyboard(subject_id: int) -> InlineKeyboardMarkup:
    """Клавиатура под списком ДЗ для студента (обновить или вернуться к предметам)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data=f"hw_refresh:{subject_id}",
                ),
                InlineKeyboardButton(
                    text="« К предметам",
                    callback_data="hw_list_subjects",
                ),
            ]
        ]
    )


def get_admin_homework_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню раздела управления ДЗ в панели старосты."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить новое ДЗ",
                    callback_data="ahw_menu_add",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Список / Редактировать / Удалить",
                    callback_data="ahw_menu_list",
                )
            ],
            [
                InlineKeyboardButton(
                    text="« Назад в панель старосты",
                    callback_data="admin_main_back",
                )
            ],
        ]
    )


def get_admin_homework_list_keyboard(
    homework_list: List[Dict[str, Any]], subject_id: int
) -> InlineKeyboardMarkup:
    """Клавиатура со списком ДЗ по выбранному предмету для старосты."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for idx, hw in enumerate(homework_list, start=1):
        due = hw.get("due_date", "—")
        hw_id = hw.get("id")
        keyboard.append([
            InlineKeyboardButton(
                text=f"📝 Задание #{idx} (до {due})",
                callback_data=f"ahw_detail:{hw_id}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="➕ Добавить ДЗ по этому предмету",
            callback_data=f"ahw_start_add:{subject_id}",
        )
    ])
    keyboard.append([
        InlineKeyboardButton(
            text="« Назад к выбору предмета",
            callback_data="ahw_menu_list",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_homework_detail_keyboard(
    homework_id: int, subject_id: int
) -> InlineKeyboardMarkup:
    """Клавиатура управления конкретным домашним заданием (редактирование, удаление)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить текст",
                    callback_data=f"ahw_edit_text:{homework_id}",
                ),
                InlineKeyboardButton(
                    text="📅 Изменить дедлайн",
                    callback_data=f"ahw_edit_date:{homework_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить задание",
                    callback_data=f"ahw_del_confirm:{homework_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="« К списку заданий предмета",
                    callback_data=f"ahw_list_subj:{subject_id}",
                )
            ],
        ]
    )


def get_admin_confirm_delete_hw_keyboard(
    homework_id: int, subject_id: int
) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления задания."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=f"ahw_del_do:{homework_id}:{subject_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"ahw_detail:{homework_id}",
                ),
            ]
        ]
    )


def get_cancel_hw_keyboard(back_callback: str = "admin_hw_menu") -> InlineKeyboardMarkup:
    """Клавиатура отмены FSM-ввода."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=back_callback,
                )
            ]
        ]
    )
