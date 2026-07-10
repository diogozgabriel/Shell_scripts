"""Testes de criação do banco, versão do esquema e sincronia do FTS."""

from __future__ import annotations

from app.database.connection import Database, check_fts5_available
from app.database.repository import FileRecord, FileRepository
from app.database.schema import SCHEMA_VERSION, get_schema_version


def test_fts5_available() -> None:
    assert check_fts5_available()


def test_schema_created_with_version(database: Database) -> None:
    conn = database.connect()
    try:
        assert get_schema_version(conn) == SCHEMA_VERSION
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
            )
        }
        assert {"files", "files_fts", "settings"} <= tables
    finally:
        conn.close()


def test_upsert_and_update(database: Database) -> None:
    conn = database.connect()
    try:
        repo = FileRepository(conn)
        record = FileRecord(
            path="/docs/a.txt", name="a.txt", extension="txt",
            size=10, mtime=1.0, content="primeiro conteudo",
        )
        repo.upsert(record)
        assert repo.count() == 1
        assert repo.get_signature("/docs/a.txt") == (10, 1.0, "ok")

        record.size = 20
        record.mtime = 2.0
        record.content = "conteudo atualizado"
        repo.upsert(record)
        assert repo.count() == 1
        assert repo.get_signature("/docs/a.txt") == (20, 2.0, "ok")
    finally:
        conn.close()


def test_fts_stays_in_sync_on_update_and_delete(database: Database) -> None:
    conn = database.connect()
    try:
        repo = FileRepository(conn)
        repo.upsert(
            FileRecord(
                path="/docs/b.txt", name="b.txt", extension="txt",
                size=1, mtime=1.0, content="banana",
            )
        )
        match = "SELECT COUNT(*) FROM files_fts WHERE files_fts MATCH ?"
        assert conn.execute(match, ('"banana"',)).fetchone()[0] == 1

        repo.upsert(
            FileRecord(
                path="/docs/b.txt", name="b.txt", extension="txt",
                size=2, mtime=2.0, content="laranja",
            )
        )
        assert conn.execute(match, ('"banana"',)).fetchone()[0] == 0
        assert conn.execute(match, ('"laranja"',)).fetchone()[0] == 1

        repo.delete_paths(["/docs/b.txt"])
        assert conn.execute(match, ('"laranja"',)).fetchone()[0] == 0
        assert repo.count() == 0
    finally:
        conn.close()
