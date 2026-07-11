"""Criação de conexões SQLite.

Cada thread (GUI, indexação, busca) deve obter sua própria conexão por meio
de :class:`Database`, pois conexões SQLite não são compartilháveis entre
threads. O modo WAL permite leituras (buscas) simultâneas à escrita da
indexação.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from app.database.schema import apply_migrations

logger = logging.getLogger(__name__)


class FTS5NotAvailableError(RuntimeError):
    """SQLite compilado sem a extensão FTS5."""


def check_fts5_available() -> bool:
    """Verifica se o SQLite disponível possui suporte a FTS5."""
    try:
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE VIRTUAL TABLE _fts5_probe USING fts5(x)")
            return True
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return False


class Database:
    """Fábrica de conexões para um arquivo de banco específico."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._initialized = False

    def connect(self) -> sqlite3.Connection:
        """Abre uma nova conexão configurada; aplica migrações na primeira vez."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        if not self._initialized:
            if not check_fts5_available():
                conn.close()
                raise FTS5NotAvailableError(
                    "O SQLite desta instalação não possui FTS5. "
                    "Instale um Python/SQLite com suporte a FTS5 "
                    "(padrão nas distribuições Linux atuais)."
                )
            apply_migrations(conn)
            self._initialized = True
        return conn
