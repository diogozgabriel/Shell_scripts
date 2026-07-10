"""Testes do indexador incremental: inclusão, atualização, remoção e erros."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import pytest

from app.database.connection import Database
from app.database.repository import FileRepository
from app.indexing.indexer import Indexer
from app.services.settings_service import AppConfig, IndexedFolder


def _make_config(folder: Path, recursive: bool = True) -> AppConfig:
    config = AppConfig()
    config.folders = [IndexedFolder(path=str(folder), recursive=recursive)]
    return config


def _run(database: Database, config: AppConfig):
    return Indexer(database, config).run(cancel=threading.Event())


def test_add_update_and_skip(database: Database, tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    target = docs / "nota.txt"
    target.write_text("conteudo original", encoding="utf-8")

    config = _make_config(docs)
    stats = _run(database, config)
    assert stats.added == 1 and stats.errors == 0

    # Segunda execução sem mudanças: nada é reprocessado.
    stats = _run(database, config)
    assert stats.added == 0 and stats.updated == 0 and stats.skipped == 1

    # Modificação (mtime/size) força reprocessamento.
    target.write_text("conteudo modificado e maior", encoding="utf-8")
    os.utime(target, (target.stat().st_atime, target.stat().st_mtime + 10))
    stats = _run(database, config)
    assert stats.updated == 1

    conn = database.connect()
    try:
        row = conn.execute(
            "SELECT content FROM files WHERE path = ?", (str(target),)
        ).fetchone()
        assert "modificado" in row["content"]
    finally:
        conn.close()


def test_removed_files_are_purged(database: Database, tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    keep = docs / "fica.txt"
    remove = docs / "some.txt"
    keep.write_text("permanece", encoding="utf-8")
    remove.write_text("desaparece", encoding="utf-8")

    config = _make_config(docs)
    assert _run(database, config).added == 2

    remove.unlink()
    stats = _run(database, config)
    assert stats.removed == 1

    conn = database.connect()
    try:
        assert FileRepository(conn).count() == 1
    finally:
        conn.close()


def test_hidden_and_excluded_dirs_are_ignored(
    database: Database, tmp_path: Path
) -> None:
    docs = tmp_path / "docs"
    (docs / ".git").mkdir(parents=True)
    (docs / "node_modules").mkdir()
    (docs / ".git" / "config.txt").write_text("segredo", encoding="utf-8")
    (docs / "node_modules" / "mod.txt").write_text("lib", encoding="utf-8")
    (docs / ".oculto.txt").write_text("oculto", encoding="utf-8")
    (docs / "visivel.txt").write_text("visivel", encoding="utf-8")
    (docs / "temp.tmp").write_text("temp", encoding="utf-8")

    stats = _run(database, _make_config(docs))
    assert stats.added == 1

    conn = database.connect()
    try:
        row = conn.execute("SELECT path FROM files").fetchone()
        assert row["path"].endswith("visivel.txt")
    finally:
        conn.close()


def test_non_recursive_ignores_subfolders(
    database: Database, tmp_path: Path
) -> None:
    docs = tmp_path / "docs"
    sub = docs / "sub"
    sub.mkdir(parents=True)
    (docs / "raiz.txt").write_text("raiz", encoding="utf-8")
    (sub / "fundo.txt").write_text("fundo", encoding="utf-8")

    stats = _run(database, _make_config(docs, recursive=False))
    assert stats.added == 1


def test_oversized_file_indexed_as_metadata_only(
    database: Database, tmp_path: Path
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    big = docs / "grande.txt"
    big.write_text("x" * 2048, encoding="utf-8")

    config = _make_config(docs)
    config.max_file_size_mb = 0  # limite de 0 bytes força metadata_only
    _run(database, config)

    conn = database.connect()
    try:
        row = conn.execute(
            "SELECT status, content FROM files WHERE path = ?", (str(big),)
        ).fetchone()
        assert row["status"] == "metadata_only"
        assert row["content"] == ""
    finally:
        conn.close()


def test_corrupted_file_records_error_and_continues(
    database: Database, tmp_path: Path
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    # PDF corrompido: extensão pdf com bytes inválidos.
    (docs / "quebrado.pdf").write_bytes(b"nao sou um pdf de verdade")
    (docs / "ok.txt").write_text("integro", encoding="utf-8")

    stats = _run(database, _make_config(docs))

    conn = database.connect()
    try:
        rows = {
            row["name"]: row["status"]
            for row in conn.execute("SELECT name, status FROM files")
        }
    finally:
        conn.close()
    # Ambos entram no índice; o corrompido com status de erro ou apenas
    # metadados (quando PyMuPDF não está instalado no ambiente de teste).
    assert rows["ok.txt"] == "ok"
    assert rows["quebrado.pdf"] in ("error", "metadata_only")
    assert stats.added == 2


@pytest.mark.skipif(
    sys.platform.startswith("win") or os.geteuid() == 0,
    reason="chmod 000 não bloqueia leitura para root/Windows",
)
def test_unreadable_file_does_not_abort(database: Database, tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    blocked = docs / "sem_acesso.txt"
    blocked.write_text("proibido", encoding="utf-8")
    blocked.chmod(0)
    (docs / "livre.txt").write_text("liberado", encoding="utf-8")

    try:
        stats = _run(database, _make_config(docs))
    finally:
        blocked.chmod(0o644)

    assert stats.added == 2  # ambos entram; o inacessível com status de erro
    conn = database.connect()
    try:
        row = conn.execute(
            "SELECT status FROM files WHERE path = ?", (str(blocked),)
        ).fetchone()
        assert row["status"] == "error"
    finally:
        conn.close()
