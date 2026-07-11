"""Fixtures compartilhadas dos testes (sem dependência de Qt)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Permite executar `pytest` a partir da raiz do projeto sem instalação.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.connection import Database  # noqa: E402


@pytest.fixture()
def database(tmp_path: Path) -> Database:
    """Banco SQLite temporário com o esquema aplicado."""
    return Database(tmp_path / "test.db")
