"""Testes do serviço de busca: nome, conteúdo, normalização e filtros."""

from __future__ import annotations

from app.database.connection import Database
from app.database.repository import FileRecord, FileRepository
from app.search.search_service import (
    SearchFilters,
    SearchService,
    build_fts_match,
    normalize_query_tokens,
)


def _seed(database: Database) -> None:
    conn = database.connect()
    try:
        repo = FileRepository(conn)
        repo.upsert(
            FileRecord(
                path="/docs/relatorio_anual.txt", name="relatorio_anual.txt",
                extension="txt", size=100, mtime=1000.0,
                content="receita e despesas do exercício",
            )
        )
        repo.upsert(
            FileRecord(
                path="/docs/receitas/bolo.md", name="bolo.md",
                extension="md", size=200, mtime=2000.0,
                content="bolo de cenoura com chocolate",
            )
        )
        repo.upsert(
            FileRecord(
                path="/fotos/ferias.png", name="ferias.png",
                extension="png", size=5000, mtime=3000.0, content="",
            )
        )
    finally:
        conn.close()


def test_normalize_query_tokens() -> None:
    assert normalize_query_tokens("  Bolo   de CENOURA! ") == ["bolo", "de", "cenoura"]
    assert normalize_query_tokens("") == []
    assert normalize_query_tokens('a AND "b" OR (c)*') == ["a", "and", "b", "or", "c"]


def test_fts_match_neutralizes_special_syntax() -> None:
    # Operadores e aspas viram tokens citados com prefixo.
    assert build_fts_match(["near", "not"]) == '"near"* "not"*'


def test_search_by_name(database: Database) -> None:
    _seed(database)
    service = SearchService(database)
    results = service.search("relatorio", SearchFilters(mode="name"))
    assert [r.name for r in results] == ["relatorio_anual.txt"]
    # Insensível a maiúsculas e subpalavra.
    assert service.search("RELAT", SearchFilters(mode="name"))


def test_search_by_content_with_snippet(database: Database) -> None:
    _seed(database)
    service = SearchService(database)
    results = service.search("cenoura", SearchFilters(mode="content"))
    assert [r.name for r in results] == ["bolo.md"]
    assert "cenoura" in results[0].snippet


def test_search_both_prefers_name_matches(database: Database) -> None:
    _seed(database)
    service = SearchService(database)
    # "receita": está no nome/caminho de receitas/bolo.md e no conteúdo do
    # relatório; correspondência de nome vem primeiro.
    results = service.search("receita")
    assert results[0].name == "bolo.md"
    assert {r.name for r in results} == {"bolo.md", "relatorio_anual.txt"}


def test_search_multiple_words(database: Database) -> None:
    _seed(database)
    service = SearchService(database)
    results = service.search("bolo chocolate", SearchFilters(mode="content"))
    assert [r.name for r in results] == ["bolo.md"]


def test_special_characters_do_not_break_query(database: Database) -> None:
    _seed(database)
    service = SearchService(database)
    # Sintaxe FTS e curingas LIKE não devem gerar exceção nem falsos positivos.
    assert service.search('"bolo" OR (receita)*') is not None
    assert service.search("100%_teste") == []
    assert service.search("***") == []


def test_filters(database: Database) -> None:
    _seed(database)
    service = SearchService(database)

    by_extension = service.search(
        "bolo", SearchFilters(mode="both", extensions=["md"])
    )
    assert [r.name for r in by_extension] == ["bolo.md"]

    by_folder = service.search("ferias", SearchFilters(folder="/fotos"))
    assert [r.name for r in by_folder] == ["ferias.png"]
    assert service.search("ferias", SearchFilters(folder="/docs")) == []

    by_date = service.search(
        "bolo", SearchFilters(date_from=1500.0, date_to=2500.0)
    )
    assert [r.name for r in by_date] == ["bolo.md"]

    by_size = service.search("ferias", SearchFilters(size_max=100))
    assert by_size == []
