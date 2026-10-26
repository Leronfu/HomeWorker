"""Модуль работы с базой данных SQLite через aiosqlite."""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, List, Optional, Any
import aiosqlite

DEFAULT_DB_PATH = os.getenv("DB_PATH", "homeworker.db")

# Список 10 предустановленных предметов согласно требованиям
DEFAULT_SUBJECTS: List[str] = [
    "Психология эмоций и мотивации",
    "Психология личности",
    "Психодиагностика",
    "Экспериментальная психология",
    "Статистика",
    "Методология",
    "Медицинская психология",
    "Социальная психология",
    "Основы управления интеллектуальной собственностью",
    "Основы психологической помощи",
]


@asynccontextmanager
async def get_connection(db_path: Optional[str] = None) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Асинхронный контекстный менеджер подключения к базе данных.
    
    Включает поддержку внешних ключей и доступ к колонкам по имени.
    """
    if db_path is None:
        try:
            from bot import config
            path = config.DB_PATH
        except ImportError:
            path = os.getenv("DB_PATH", "homeworker.db")
    else:
        path = db_path

    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON;")
        yield db


async def init_db(db_path: Optional[str] = None) -> None:
    """Инициализация таблиц базы данных и начальное заполнение предметами."""
    async with get_connection(db_path) as db:
        # 1. Таблица пользователей
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 2. Таблица предметов
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
            """
        )

        # 3. Таблица расписания
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_type TEXT NOT NULL CHECK(week_type IN ('current', 'next')),
                day_of_week INTEGER NOT NULL CHECK(day_of_week BETWEEN 1 AND 6),
                content TEXT NOT NULL DEFAULT '',
                UNIQUE(week_type, day_of_week)
            );
            """
        )

        # 4. Таблица домашних заданий
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS homework (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                due_date TEXT NOT NULL,
                task_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 5. Таблица партий докладов (дропов)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS report_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                seminar_date TEXT NOT NULL,
                release_date TEXT NOT NULL,
                release_datetime_random TEXT NOT NULL,
                is_published BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 6. Таблица тем докладов
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS report_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL REFERENCES report_batches(id) ON DELETE CASCADE,
                topic_number INTEGER NOT NULL,
                topic_text TEXT NOT NULL,
                user_id INTEGER REFERENCES users(telegram_id) ON DELETE SET NULL,
                assigned_at TIMESTAMP
            );
            """
        )

        # Первичное заполнение предметов
        for subject_name in DEFAULT_SUBJECTS:
            await db.execute(
                "INSERT OR IGNORE INTO subjects (name) VALUES (?);",
                (subject_name,),
            )

        # Первичное заполнение пустых дней недели для текущей и следующей недель
        for week in ("current", "next"):
            for day in range(1, 7):
                await db.execute(
                    "INSERT OR IGNORE INTO schedule (week_type, day_of_week, content) VALUES (?, ?, '');",
                    (week, day),
                )

        await db.commit()


# =====================================================================
# Функции работы с пользователями (users)
# =====================================================================

async def add_or_update_user(
    telegram_id: int,
    username: Optional[str],
    full_name: str,
    is_admin: bool = False,
    db_path: Optional[str] = None,
) -> None:
    """Добавить или обновить пользователя."""
    async with get_connection(db_path) as db:
        await db.execute(
            """
            INSERT INTO users (telegram_id, username, full_name, is_admin)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                is_admin = CASE WHEN users.is_admin = 1 THEN 1 ELSE excluded.is_admin END;
            """,
            (telegram_id, username, full_name, int(is_admin)),
        )
        await db.commit()


async def get_user(telegram_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Получить пользователя по telegram_id."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?;",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_all_users(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Получить всех пользователей для рассылки."""
    async with get_connection(db_path) as db:
        cursor = await db.execute("SELECT * FROM users ORDER BY id ASC;")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def set_user_admin(telegram_id: int, is_admin: bool, db_path: Optional[str] = None) -> None:
    """Установить статус администратора для пользователя."""
    async with get_connection(db_path) as db:
        await db.execute(
            "UPDATE users SET is_admin = ? WHERE telegram_id = ?;",
            (int(is_admin), telegram_id),
        )
        await db.commit()


async def get_all_admin_ids(db_path: Optional[str] = None) -> List[int]:
    """Получить уникальный список telegram_id всех администраторов (из config.ADMIN_IDS и БД)."""
    from bot import config

    admin_ids = set(config.ADMIN_IDS)
    try:
        async with get_connection(db_path) as db:
            cursor = await db.execute("SELECT telegram_id FROM users WHERE is_admin = 1;")
            rows = await cursor.fetchall()
            for r in rows:
                admin_ids.add(r["telegram_id"])
    except Exception:
        pass
    return sorted(list(admin_ids))


# =====================================================================
# Функции работы с предметами (subjects)
# =====================================================================

async def get_all_subjects(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Получить список всех 10 предметов."""
    async with get_connection(db_path) as db:
        cursor = await db.execute("SELECT * FROM subjects ORDER BY id ASC;")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_subject_by_id(subject_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Получить предмет по id."""
    async with get_connection(db_path) as db:
        cursor = await db.execute("SELECT * FROM subjects WHERE id = ?;", (subject_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_or_create_subject(name: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Получить существующий предмет по названию или создать новый."""
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Название предмета не может быть пустым")

    async with get_connection(db_path) as db:
        cursor = await db.execute(
            "SELECT * FROM subjects WHERE LOWER(TRIM(name)) = LOWER(TRIM(?));",
            (cleaned,),
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)

        cursor = await db.execute("INSERT INTO subjects (name) VALUES (?);", (cleaned,))
        await db.commit()
        new_id = cursor.lastrowid
        return {"id": new_id, "name": cleaned}


# =====================================================================
# Функции работы с расписанием (schedule)
# =====================================================================

async def get_schedule(week_type: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Получить расписание на неделю (1-6 дни)."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            "SELECT * FROM schedule WHERE week_type = ? ORDER BY day_of_week ASC;",
            (week_type,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_schedule_day(
    week_type: str, day_of_week: int, db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Получить расписание на конкретный день недели."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            "SELECT * FROM schedule WHERE week_type = ? AND day_of_week = ?;",
            (week_type, day_of_week),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_schedule_day(
    week_type: str, day_of_week: int, content: str, db_path: Optional[str] = None
) -> None:
    """Обновить текст расписания на указанный день."""
    async with get_connection(db_path) as db:
        await db.execute(
            """
            INSERT INTO schedule (week_type, day_of_week, content)
            VALUES (?, ?, ?)
            ON CONFLICT(week_type, day_of_week) DO UPDATE SET content = excluded.content;
            """,
            (week_type, day_of_week, content),
        )
        await db.commit()


async def copy_next_to_current_week(db_path: Optional[str] = None) -> None:
    """Скопировать расписание следующей недели в текущую и очистить следующую неделю.
    
    Используется планировщиком APScheduler каждую субботу в 15:00.
    """
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            "SELECT day_of_week, content FROM schedule WHERE week_type = 'next';"
        )
        next_days = await cursor.fetchall()
        for day in next_days:
            await db.execute(
                """
                UPDATE schedule
                SET content = ?
                WHERE week_type = 'current' AND day_of_week = ?;
                """,
                (day["content"], day["day_of_week"]),
            )
        # Очищаем расписание следующей недели
        await db.execute("UPDATE schedule SET content = '' WHERE week_type = 'next';")
        await db.commit()


async def clear_week_schedule(week_type: str, db_path: Optional[str] = None) -> None:
    """Очистить все дни выбранной недели."""
    async with get_connection(db_path) as db:
        await db.execute("UPDATE schedule SET content = '' WHERE week_type = ?;", (week_type,))
        await db.commit()



# =====================================================================
# Функции работы с домашними заданиями (homework)
# =====================================================================

async def add_homework(
    subject_id: int, due_date: str, task_text: str, db_path: Optional[str] = None
) -> int:
    """Добавить новое домашнее задание."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            "INSERT INTO homework (subject_id, due_date, task_text) VALUES (?, ?, ?);",
            (subject_id, due_date, task_text),
        )
        await db.commit()
        return cursor.lastrowid or 0


async def get_homework_by_subject(
    subject_id: int, db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Получить все домашние задания по предмету."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            """
            SELECT h.*, s.name as subject_name
            FROM homework h
            JOIN subjects s ON h.subject_id = s.id
            WHERE h.subject_id = ?
            ORDER BY h.id DESC;
            """,
            (subject_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_all_homework(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Получить все домашние задания по всем предметам."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            """
            SELECT h.*, s.name as subject_name
            FROM homework h
            JOIN subjects s ON h.subject_id = s.id
            ORDER BY h.id DESC;
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_homework_by_id(
    homework_id: int, db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Получить задание по id."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            """
            SELECT h.*, s.name as subject_name
            FROM homework h
            JOIN subjects s ON h.subject_id = s.id
            WHERE h.id = ?;
            """,
            (homework_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def delete_homework(homework_id: int, db_path: Optional[str] = None) -> bool:
    """Удалить домашнее задание."""
    async with get_connection(db_path) as db:
        cursor = await db.execute("DELETE FROM homework WHERE id = ?;", (homework_id,))
        await db.commit()
        return cursor.rowcount > 0


async def update_homework(
    homework_id: int,
    due_date: Optional[str] = None,
    task_text: Optional[str] = None,
    db_path: Optional[str] = None,
) -> bool:
    """Обновить дедлайн и/или текст домашнего задания."""
    if due_date is None and task_text is None:
        return False

    fields = []
    values: List[Any] = []
    if due_date is not None:
        fields.append("due_date = ?")
        values.append(due_date)
    if task_text is not None:
        fields.append("task_text = ?")
        values.append(task_text)

    values.append(homework_id)
    set_clause = ", ".join(fields)
    query = f"UPDATE homework SET {set_clause} WHERE id = ?;"

    async with get_connection(db_path) as db:
        cursor = await db.execute(query, tuple(values))
        await db.commit()
        return cursor.rowcount > 0


# =====================================================================
# Функции работы с докладами (report_batches & report_topics)
# =====================================================================

async def create_report_batch(
    subject_id: int,
    seminar_date: str,
    release_date: str,
    release_datetime_random: str,
    topics: List[str],
    db_path: Optional[str] = None,
) -> int:
    """Создать новую партию докладов с темами."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO report_batches (subject_id, seminar_date, release_date, release_datetime_random)
            VALUES (?, ?, ?, ?);
            """,
            (subject_id, seminar_date, release_date, release_datetime_random),
        )
        batch_id = cursor.lastrowid
        if not batch_id:
            raise RuntimeError("Не удалось создать партию докладов")

        for idx, topic_text in enumerate(topics, start=1):
            await db.execute(
                """
                INSERT INTO report_topics (batch_id, topic_number, topic_text)
                VALUES (?, ?, ?);
                """,
                (batch_id, idx, topic_text.strip()),
            )

        await db.commit()
        return batch_id


async def get_pending_report_batches(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Получить список партий докладов, ожидающих публикации."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            """
            SELECT b.*, s.name as subject_name
            FROM report_batches b
            JOIN subjects s ON b.subject_id = s.id
            WHERE b.is_published = 0
            ORDER BY b.release_datetime_random ASC;
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_all_report_batches(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Получить все партии докладов (для админки) со статистикой по темам."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            """
            SELECT b.*, s.name as subject_name,
                   COUNT(t.id) as topics_count,
                   SUM(CASE WHEN t.user_id IS NOT NULL THEN 1 ELSE 0 END) as claimed_count
            FROM report_batches b
            JOIN subjects s ON b.subject_id = s.id
            LEFT JOIN report_topics t ON b.id = t.batch_id
            GROUP BY b.id
            ORDER BY b.id DESC;
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def publish_report_batch(batch_id: int, db_path: Optional[str] = None) -> bool:
    """Пометить партию докладов как опубликованную."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            "UPDATE report_batches SET is_published = 1 WHERE id = ?;",
            (batch_id,),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_batches_by_subject(
    subject_id: int, only_published: bool = True, db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Получить партии докладов по предмету."""
    async with get_connection(db_path) as db:
        query = """
            SELECT b.*, s.name as subject_name
            FROM report_batches b
            JOIN subjects s ON b.subject_id = s.id
            WHERE b.subject_id = ?
        """
        params: List[Any] = [subject_id]
        if only_published:
            query += " AND b.is_published = 1"
        query += " ORDER BY b.id DESC;"

        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_batch_by_id(batch_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Получить информацию о партии докладов по id."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            """
            SELECT b.*, s.name as subject_name
            FROM report_batches b
            JOIN subjects s ON b.subject_id = s.id
            WHERE b.id = ?;
            """,
            (batch_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_batch_topics(batch_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Получить список всех тем партии с информацией о занявших студентах."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            """
            SELECT t.*, u.full_name as student_name, u.username as student_username
            FROM report_topics t
            LEFT JOIN users u ON t.user_id = u.telegram_id
            WHERE t.batch_id = ?
            ORDER BY t.topic_number ASC;
            """,
            (batch_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def claim_topic(topic_id: int, user_telegram_id: int, db_path: Optional[str] = None) -> bool:
    """Атомарно закрепить тему за студентом (с защитой от конкурентной записи).
    
    Возвращает True, если тема успешно занята этим студентом.
    Возвращает False, если тема уже кем-то занята.
    """
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            """
            UPDATE report_topics
            SET user_id = ?, assigned_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id IS NULL;
            """,
            (user_telegram_id, topic_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def unclaim_topic(topic_id: int, user_telegram_id: int, db_path: Optional[str] = None) -> bool:
    """Освободить тему (студент может отказаться от своей темы)."""
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            """
            UPDATE report_topics
            SET user_id = NULL, assigned_at = NULL
            WHERE id = ? AND user_id = ?;
            """,
            (topic_id, user_telegram_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_report_batch(batch_id: int, db_path: Optional[str] = None) -> bool:
    """Удалить партию докладов (связанные темы удалятся каскадно)."""
    async with get_connection(db_path) as db:
        cursor = await db.execute("DELETE FROM report_batches WHERE id = ?;", (batch_id,))
        await db.commit()
        return cursor.rowcount > 0
