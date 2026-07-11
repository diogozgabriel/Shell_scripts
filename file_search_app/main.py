"""Ponto de entrada do aplicativo de busca de arquivos."""

from __future__ import annotations

import logging
import sys

from app.utils.logging_config import setup_logging


def main() -> int:
    """Inicializa logging, banco e interface gráfica."""
    setup_logging()
    logger = logging.getLogger("main")

    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.database.connection import (
        Database,
        FTS5NotAvailableError,
        check_fts5_available,
    )
    from app.gui.main_window import MainWindow
    from app.utils.platform_utils import get_database_path

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Busca de Arquivos")

    if not check_fts5_available():
        QMessageBox.critical(
            None,
            "SQLite sem FTS5",
            "O SQLite desta instalação do Python não possui a extensão FTS5, "
            "necessária para a busca por conteúdo. Instale o Python do "
            "repositório da sua distribuição (no Garuda: sudo pacman -S python).",
        )
        return 1

    try:
        database = Database(get_database_path())
        database.connect().close()  # cria o banco e aplica migrações
    except FTS5NotAvailableError as exc:
        QMessageBox.critical(None, "SQLite sem FTS5", str(exc))
        return 1
    except Exception as exc:
        logger.exception("Falha ao inicializar o banco de dados")
        QMessageBox.critical(None, "Erro", f"Falha ao abrir o banco: {exc}")
        return 1

    window = MainWindow(database)
    window.show()
    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
