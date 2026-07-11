"""Configuração de logging da aplicação."""

from __future__ import annotations

import logging
import logging.handlers

from app.utils.platform_utils import get_data_dir


def setup_logging(level: int = logging.INFO) -> None:
    """Configura logging para console e arquivo rotativo no diretório de dados."""
    log_file = get_data_dir() / "file-search-app.log"
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    root = logging.getLogger()
    if root.handlers:  # já configurado (por exemplo, em testes)
        return
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:
        root.warning("Não foi possível criar o arquivo de log em %s", log_file)
