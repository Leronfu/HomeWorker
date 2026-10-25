"""Состояния FSM (Finite State Machine) для бота."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Состояния для сценария первичной регистрации студента."""
    waiting_for_full_name = State()


class ScheduleAdminStates(StatesGroup):
    """Состояния для редактирования расписания старостой."""
    waiting_for_day_content = State()
