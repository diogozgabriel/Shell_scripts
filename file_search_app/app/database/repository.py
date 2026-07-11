"""Acesso a dados: metadados de arquivos e configurações persistidas.

Todas as consultas usam parâmetros vinculados; nenhum valor vindo do usuário
ou do sistema de arquivos é interpolado em SQL.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Iterable, Optional

# Status possíveis de extração gravados em files.status
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_METADATA_ONLY = "metadata_only"
STATUS_SKIPPED = "skipped"


@dataclass(slots=True)
class FileRecord:
    """Registro completo de um arquivo no índice."""

    path: str
    name: str
    extension: str
    size: int
    mtime: float
    content: str = ""
    status: str = STATUS_OK
    error: Optional[str] = None


class FileRepository:
    """Operações sobre a tabela ``files`` (e, via triggers, ``files_fts``)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, record: FileRecord) -> None:
        """Insere ou atualiza um arquivo pelo caminho."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO files (path, name, extension, size, mtime, content,
                                   indexed_at, status, error)
                VALUES (:path, :name, :extension, :size, :mtime, :content,
                        :indexed_at, :status, :error)
                ON CONFLICT(path) DO UPDATE SET
                    name = excluded.name,
                    extension = excluded.extension,
                    size = excluded.size,
                    mtime = excluded.mtime,
                    content = excluded.content,
                    indexed_at = excluded.indexed_at,
                    status = excluded.status,
                    error = excluded.error
                """,
                {
                    "path": record.path,
                    "name": record.name,
                    "extension": record.extension,
                    "size": record.size,
                    "mtime": record.mtime,
                    "content": record.content,
                    "indexed_at": time.time(),
                    "status": record.status,
                    "error": record.error,
                },
            )

    def get_signature(self, path: str) -> Optional[tuple[int, float, str]]:
        """Retorna ``(size, mtime, status)`` do arquivo indexado, ou None."""
        row = self._conn.execute(
            "SELECT size, mtime, status FROM files WHERE path = ?", (path,)
        ).fetchone()
        if row is None:
            return None
        return int(row["size"]), float(row["mtime"]), str(row["status"])

    def get_all_signatures(self) -> dict[str, tuple[int, float, str]]:
        """Mapa caminho -> (size, mtime, status) de todo o índice.

        Carregado uma vez por indexação para evitar uma consulta por arquivo.
        """
        rows = self._conn.execute("SELECT path, size, mtime, status FROM files")
        return {
            row["path"]: (int(row["size"]), float(row["mtime"]), str(row["status"]))
            for row in rows
        }

    def delete_paths(self, paths: Iterable[str]) -> int:
        """Remove os caminhos informados do índice. Retorna quantos removeu."""
        removed = 0
        with self._conn:
            for path in paths:
                cur = self._conn.execute("DELETE FROM files WHERE path = ?", (path,))
                removed += cur.rowcount
        return removed

    def count(self) -> int:
        """Total de arquivos indexados."""
        return int(self._conn.execute("SELECT COUNT(*) FROM files").fetchone()[0])

    def optimize_fts(self) -> None:
        """Compacta as estruturas internas do FTS5 após grandes alterações."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO files_fts(files_fts) VALUES ('optimize')"
            )


class SettingsRepository:
    """Armazena pares chave/valor (JSON serializado) na tabela ``settings``."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, key: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return None if row is None else str(row["value"])

    def set(self, key: str, value: str) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
