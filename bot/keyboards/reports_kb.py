"""Клавиатуры для управления докладами старостой (Шаг 6)."""

from typing import Any, Dict, List
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_admin_reports_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню раздела управления докладами в панели старосты."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Запланировать новый дроп",
                    callback_data="arep_menu_add",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Список партий докладов",
                    callback_data="arep_menu_list",
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


def get_admin_batches_list_keyboard(batches: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура со списком всех партий докладов."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for b in batches:
        is_pub = bool(b.get("is_published", False))
        icon = "📢" if is_pub else "⏳"
        subj_name = str(b.get("subject_name", "Предмет"))
        sem_date = str(b.get("seminar_date", "—"))
        batch_id = b["id"]

        # Компактное отображение в кнопке
        btn_text = f"{icon} {subj_name[:14]}... ({sem_date})"
        keyboard.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"arep_detail:{batch_id}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="➕ Запланировать новый дроп",
            callback_data="arep_menu_add",
        )
    ])
    keyboard.append([
        InlineKeyboardButton(
            text="« Назад в меню докладов",
            callback_data="admin_reports_menu",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_batch_detail_keyboard(batch: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Клавиатура управления выбранной партией докладов."""
    batch_id = batch["id"]
    is_published = bool(batch.get("is_published", False))

    buttons: List[List[InlineKeyboardButton]] = []

    # Если партия еще не опубликована, даем админу возможность дропнуть ее принудительно сейчас
    if not is_published:
        buttons.append([
            InlineKeyboardButton(
                text="⚡ Опубликовать прямо сейчас",
                callback_data=f"arep_pub_now:{batch_id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="🗑 Удалить партию докладов",
            callback_data=f"arep_del_confirm:{batch_id}",
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text="« К списку партий",
            callback_data="arep_menu_list",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_confirm_delete_batch_keyboard(batch_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления партии докладов."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить партию",
                    callback_data=f"arep_del_do:{batch_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"arep_detail:{batch_id}",
                ),
            ]
        ]
    )


def get_cancel_reports_keyboard(back_callback: str = "admin_reports_menu") -> InlineKeyboardMarkup:
    """Клавиатура отмены FSM-ввода в модуле докладов."""
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
