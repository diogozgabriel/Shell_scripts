"""Utilitários dependentes do sistema operacional.

Centraliza detecção de plataforma, diretórios de dados e integração com o
gerenciador de arquivos (abrir pasta, revelar arquivo).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

APP_DIR_NAME = "file-search-app"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_macos() -> bool:
    return sys.platform == "darwin"


def get_data_dir() -> Path:
    """Retorna (criando se preciso) o diretório de dados da aplicação."""
    if is_windows():
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif is_macos():
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    data_dir = base / APP_DIR_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_database_path() -> Path:
    """Caminho padrão do banco SQLite da aplicação."""
    return get_data_dir() / "index.db"


def _run_detached(command: list[str]) -> bool:
    """Executa um comando sem bloquear a interface. Retorna False em falha."""
    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except (OSError, ValueError) as exc:
        logger.warning("Falha ao executar %s: %s", command, exc)
        return False


def open_containing_folder(file_path: Path) -> bool:
    """Abre no gerenciador de arquivos a pasta que contém ``file_path``."""
    folder = file_path if file_path.is_dir() else file_path.parent
    if is_windows():
        return _run_detached(["explorer", str(folder)])
    if is_macos():
        return _run_detached(["open", str(folder)])
    return _run_detached(["xdg-open", str(folder)])


def reveal_in_file_manager(file_path: Path) -> bool:
    """Revela (seleciona) o arquivo no gerenciador, quando o SO permitir.

    No Linux tenta a interface D-Bus ``org.freedesktop.FileManager1``
    (suportada por Dolphin, Nautilus, Thunar etc.); se indisponível, abre a
    pasta que contém o arquivo.
    """
    if is_windows():
        return _run_detached(["explorer", f"/select,{file_path}"])
    if is_macos():
        return _run_detached(["open", "-R", str(file_path)])

    if shutil.which("dbus-send"):
        uri = file_path.resolve().as_uri()
        ok = _run_detached(
            [
                "dbus-send",
                "--session",
                "--dest=org.freedesktop.FileManager1",
                "--type=method_call",
                "/org/freedesktop/FileManager1",
                "org.freedesktop.FileManager1.ShowItems",
                f"array:string:{uri}",
                "string:",
            ]
        )
        if ok:
            return True
    return open_containing_folder(file_path)
