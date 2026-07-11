"""Serviço de busca sobre o índice SQLite/FTS5.

A consulta do usuário é normalizada em tokens e executada de duas formas:

* **nome/caminho**: ``LIKE`` com curingas escapados (subpalavras em qualquer
  posição, insensível a maiúsculas);
* **conteúdo**: consulta FTS5 com tokens entre aspas e prefixo (``"tok"*``),
  o que neutraliza operadores especiais da sintaxe FTS5 e permite palavras
  parciais, ordenando por relevância (bm25) e destacando trechos com
  ``snippet()``.

Resultados por nome aparecem antes dos resultados apenas de conteúdo.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

from app.database.connection import Database

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 500
SNIPPET_MARK_START = "«"  # «
SNIPPET_MARK_END = "»"  # »

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(slots=True)
class SearchFilters:
    """Filtros opcionais aplicados à busca."""

    extensions: list[str] = field(default_factory=list)
    folder: Optional[str] = None
    date_from: Optional[float] = None  # timestamps (epoch)
    date_to: Optional[float] = None
    size_min: Optional[int] = None  # bytes
    size_max: Optional[int] = None
    mode: str = "both"  # both | name | content


@dataclass(slots=True)
class SearchResult:
    """Um item retornado pela busca."""

    file_id: int
    path: str
    name: str
    extension: str
    size: int
    mtime: float
    snippet: str = ""
    matched_name: bool = False


def normalize_query_tokens(query: str) -> list[str]:
    """Extrai tokens alfanuméricos da consulta, em minúsculas."""
    return [t.lower() for t in _TOKEN_RE.findall(query)][:10]


def build_fts_match(tokens: list[str]) -> str:
    """Monta a expressão FTS5: cada token vira ``"token"*`` (AND implícito).

    As aspas impedem que caracteres especiais da consulta sejam interpretados
    como operadores FTS5; o ``*`` habilita correspondência por prefixo.
    """
    return " ".join(f'"{t}"*' for t in tokens)


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SearchService:
    """Executa buscas combinando nome/caminho (LIKE) e conteúdo (FTS5)."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[SearchResult]:
        """Busca pela consulta do usuário; retorna no máximo ``limit`` itens."""
        filters = filters or SearchFilters()
        tokens = normalize_query_tokens(query)
        if not tokens:
            return []

        conn = self._database.connect()
        try:
            results: dict[int, SearchResult] = {}
            if filters.mode in ("both", "name"):
                for item in self._search_by_name(conn, tokens, filters, limit):
                    results[item.file_id] = item
            if filters.mode in ("both", "content"):
                for item in self._search_by_content(conn, tokens, filters, limit):
                    existing = results.get(item.file_id)
                    if existing is None:
                        results[item.file_id] = item
                    elif not existing.snippet:
                        existing.snippet = item.snippet
            ordered = sorted(
                results.values(),
                key=lambda r: (not r.matched_name, -r.mtime),
            )
            return ordered[:limit]
        finally:
            conn.close()

    # ------------------------------------------------------------------ #

    @staticmethod
    def _filter_sql(filters: SearchFilters, params: dict) -> str:
        """Gera as cláusulas SQL dos filtros, preenchendo ``params``."""
        clauses: list[str] = []
        if filters.extensions:
            placeholders = []
            for index, extension in enumerate(filters.extensions):
                key = f"ext{index}"
                placeholders.append(f":{key}")
                params[key] = extension.lower().lstrip(".")
            clauses.append(f"f.extension IN ({', '.join(placeholders)})")
        if filters.folder:
            params["folder"] = _escape_like(filters.folder.rstrip("/")) + "/%"
            clauses.append(r"f.path LIKE :folder ESCAPE '\'")
        if filters.date_from is not None:
            params["date_from"] = filters.date_from
            clauses.append("f.mtime >= :date_from")
        if filters.date_to is not None:
            params["date_to"] = filters.date_to
            clauses.append("f.mtime <= :date_to")
        if filters.size_min is not None:
            params["size_min"] = filters.size_min
            clauses.append("f.size >= :size_min")
        if filters.size_max is not None:
            params["size_max"] = filters.size_max
            clauses.append("f.size <= :size_max")
        return (" AND " + " AND ".join(clauses)) if clauses else ""

    def _search_by_name(
        self,
        conn: sqlite3.Connection,
        tokens: list[str],
        filters: SearchFilters,
        limit: int,
    ) -> list[SearchResult]:
        params: dict = {"limit": limit}
        token_clauses: list[str] = []
        for index, token in enumerate(tokens):
            key = f"tok{index}"
            params[key] = f"%{_escape_like(token)}%"
            token_clauses.append(rf"lower(f.path) LIKE :{key} ESCAPE '\'")
        sql = (
            "SELECT f.id, f.path, f.name, f.extension, f.size, f.mtime "
            "FROM files f WHERE "
            + " AND ".join(token_clauses)
            + self._filter_sql(filters, params)
            + " ORDER BY f.mtime DESC LIMIT :limit"
        )
        rows = conn.execute(sql, params).fetchall()
        return [
            SearchResult(
                file_id=row["id"],
                path=row["path"],
                name=row["name"],
                extension=row["extension"],
                size=row["size"],
                mtime=row["mtime"],
                matched_name=True,
            )
            for row in rows
        ]

    def _search_by_content(
        self,
        conn: sqlite3.Connection,
        tokens: list[str],
        filters: SearchFilters,
        limit: int,
    ) -> list[SearchResult]:
        params: dict = {"match": build_fts_match(tokens), "limit": limit}
        sql = (
            "SELECT f.id, f.path, f.name, f.extension, f.size, f.mtime, "
            f"snippet(files_fts, 2, '{SNIPPET_MARK_START}', "
            f"'{SNIPPET_MARK_END}', '…', 12) AS snip "
            "FROM files_fts JOIN files f ON f.id = files_fts.rowid "
            "WHERE files_fts MATCH :match"
            + self._filter_sql(filters, params)
            + " ORDER BY bm25(files_fts, 5.0, 2.0, 1.0) LIMIT :limit"
        )
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            # Consulta FTS inválida mesmo após sanitização: loga e não quebra.
            logger.warning("Consulta FTS rejeitada (%s): %s", params["match"], exc)
            return []
        return [
            SearchResult(
                file_id=row["id"],
                path=row["path"],
                name=row["name"],
                extension=row["extension"],
                size=row["size"],
                mtime=row["mtime"],
                snippet=str(row["snip"] or ""),
            )
            for row in rows
        ]
