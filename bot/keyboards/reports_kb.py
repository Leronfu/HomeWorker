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


def get_report_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа доклада: индивидуальный или групповой."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Индивидуальный (для 1 студента)",
                    callback_data="arep_type:individual",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Групповой (для группы студентов)",
                    callback_data="arep_type:group",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="arep_menu_add",
                )
            ],
        ]
    )


def get_student_batch_topics_keyboard(
    batch_id: int, topics: List[Dict[str, Any]], user_id: int
) -> InlineKeyboardMarkup:
    """Генерация клавиатуры выбора темы для студента.
    
    Содержит:
    - Инлайн-кнопки только со СВОБОДНЫМИ номерами тем.
    - Кнопку «Отказаться от темы», если студент уже взял тему в этой партии.
    - Кнопки «Обновить» и «К списку предметов».
    """
    keyboard: List[List[InlineKeyboardButton]] = []

    # 1. Свободные темы — группируем аккуратно по 4 в ряд
    free_topic_buttons: List[InlineKeyboardButton] = []
    user_claimed_topic_id = None
    user_claimed_topic_num = None

    for t in topics:
        topic_uid = t.get("user_id")
        if topic_uid == user_id:
            user_claimed_topic_id = t["id"]
            user_claimed_topic_num = t["topic_number"]
        elif topic_uid is None:
            num = t["topic_number"]
            free_topic_buttons.append(
                InlineKeyboardButton(
                    text=f"№{num}",
                    callback_data=f"rep_claim:{t['id']}:{batch_id}",
                )
            )

    # Разбиваем кнопки свободных тем по 4 в ряд
    chunk_size = 4
    for i in range(0, len(free_topic_buttons), chunk_size):
        keyboard.append(free_topic_buttons[i : i + chunk_size])

    # 2. Если студент уже занял тему в этой партии, показываем кнопку отказа
    if user_claimed_topic_id is not None:
        keyboard.append([
            InlineKeyboardButton(
                text=f"❌ Отказаться от своей темы №{user_claimed_topic_num}",
                callback_data=f"rep_unclaim:{user_claimed_topic_id}:{batch_id}",
            )
        ])

    # 3. Сервисные кнопки
    keyboard.append([
        InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data=f"rep_refresh:{batch_id}",
        ),
        InlineKeyboardButton(
            text="« К предметам",
            callback_data="rep_list_subjects",
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_student_batches_choice_keyboard(batches: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура выбора партии докладов по дате семинара для студента."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for b in batches:
        sem_date = str(b.get("seminar_date", "—"))
        batch_id = b["id"]
        keyboard.append([
            InlineKeyboardButton(
                text=f"🗓 Семинар на {sem_date}",
                callback_data=f"rep_view_batch:{batch_id}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="« Назад к предметам",
            callback_data="rep_list_subjects",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

