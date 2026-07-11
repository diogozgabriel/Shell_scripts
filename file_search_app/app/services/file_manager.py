"""Ações sobre arquivos dos resultados: copiar caminho, abrir e revelar pasta."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.utils import platform_utils

logger = logging.getLogger(__name__)


class FileManagerService:
    """Fachada usada pela interface para interagir com o sistema de arquivos."""

    @staticmethod
    def copy_path_to_clipboard(path: str) -> None:
        """Copia o caminho completo para a área de transferência."""
        clipboard = QApplication.clipboard()
        clipboard.setText(path)

    @staticmethod
    def open_containing_folder(path: str) -> bool:
        """Abre a pasta que contém o arquivo no gerenciador do sistema."""
        return platform_utils.open_containing_folder(Path(path))

    @staticmethod
    def reveal_file(path: str) -> bool:
        """Revela/seleciona o arquivo no gerenciador, quando suportado."""
        return platform_utils.reveal_in_file_manager(Path(path))
