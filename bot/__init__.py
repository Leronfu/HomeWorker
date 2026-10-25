"""Основной пакет Telegram-бота."""

import os
import sys

# Автоматическое переключение на .venv при импорте через глобальный python3
if sys.prefix == sys.base_prefix:
    _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _venv_py = os.path.join(_project_root, ".venv", "bin", "python3")
    if os.path.exists(_venv_py) and os.path.abspath(sys.executable) != os.path.abspath(_venv_py):
        if "unittest" in sys.argv[0]:
            args = [_venv_py, "-m", "unittest"] + sys.argv[1:]
        else:
            args = [_venv_py] + sys.argv
        os.execv(_venv_py, args)
