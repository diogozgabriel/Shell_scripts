"""Esquema do banco de dados e migrações.

A versão do esquema é controlada por ``PRAGMA user_version``. Cada migração
leva o banco da versão N-1 para N; novas migrações são acrescentadas ao final
de ``MIGRATIONS`` sem alterar as anteriores.

A tabela virtual FTS5 usa *external content* apontando para ``files`` e é
mantida sincronizada por triggers de INSERT/UPDATE/DELETE, de modo que o
conteúdo pesquisável nunca diverge da tabela principal.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

_MIGRATION_V1 = """
CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY,
    path        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    extension   TEXT NOT NULL DEFAULT '',
    size        INTEGER NOT NULL DEFAULT 0,
    mtime       REAL NOT NULL DEFAULT 0,
    content     TEXT NOT NULL DEFAULT '',
    indexed_at  REAL,
    status      TEXT NOT NULL DEFAULT 'ok',
    error       TEXT
);

CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension);
CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime);

CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
    name,
    path,
    content,
    content='files',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
    INSERT INTO files_fts(rowid, name, path, content)
    VALUES (new.id, new.name, new.path, new.content);
END;

CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
    INSERT INTO files_fts(files_fts, rowid, name, path, content)
    VALUES ('delete', old.id, old.name, old.path, old.content);
END;

CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE ON files BEGIN
    INSERT INTO files_fts(files_fts, rowid, name, path, content)
    VALUES ('delete', old.id, old.name, old.path, old.content);
    INSERT INTO files_fts(rowid, name, path, content)
    VALUES (new.id, new.name, new.path, new.content);
END;

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

MIGRATIONS: dict[int, str] = {
    1: _MIGRATION_V1,
}


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Retorna a versão atual do esquema (``PRAGMA user_version``)."""
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Aplica as migrações pendentes até ``SCHEMA_VERSION``."""
    current = get_schema_version(conn)
    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"Banco criado por versão mais nova do aplicativo "
            f"(esquema {current} > {SCHEMA_VERSION})."
        )
    for version in range(current + 1, SCHEMA_VERSION + 1):
        with conn:
            conn.executescript(MIGRATIONS[version])
            conn.execute(f"PRAGMA user_version = {version}")
