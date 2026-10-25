"""Состояния FSM (Finite State Machine) для бота."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Состояния для сценария первичной регистрации студента."""
    waiting_for_full_name = State()


class ScheduleAdminStates(StatesGroup):
    """Состояния для редактирования расписания старостой."""
    waiting_for_day_content = State()


class HomeworkAdminStates(StatesGroup):
    """Состояния FSM для добавления и редактирования домашних заданий старостой."""
    waiting_for_custom_subject = State()
    waiting_for_due_date = State()
    waiting_for_task_text = State()
    waiting_for_edit_task_text = State()
    waiting_for_edit_due_date = State()


class ReportAdminStates(StatesGroup):
    """Состояния FSM для создания и планирования партий докладов старостой."""
    waiting_for_seminar_date = State()
    waiting_for_topics_list = State()
    waiting_for_release_date = State()


