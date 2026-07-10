"""Testes dos extratores de texto e do registro por extensão."""

from __future__ import annotations

from pathlib import Path

from app.indexing.extractors import build_registry
from app.indexing.extractors.text_extractor import HtmlExtractor, TextExtractor
from app.services.settings_service import AppConfig


def test_registry_covers_required_formats() -> None:
    registry = build_registry()
    for extension in ("txt", "md", "csv", "json", "xml", "html", "pdf",
                      "docx", "xlsx", "png", "jpg", "jpeg", "tiff", "bmp"):
        assert extension in registry, f"sem extrator para {extension}"


def test_text_extraction_utf8(tmp_path: Path) -> None:
    target = tmp_path / "nota.txt"
    target.write_text("acentuação e ção", encoding="utf-8")
    result = TextExtractor().extract(target, AppConfig())
    assert result.status == "ok"
    assert "acentuação" in result.text


def test_text_extraction_latin1_fallback(tmp_path: Path) -> None:
    target = tmp_path / "antigo.txt"
    target.write_bytes("codificação antiga".encode("latin-1"))
    result = TextExtractor().extract(target, AppConfig())
    assert result.status == "ok"
    assert "codificação" in result.text


def test_text_extraction_missing_file(tmp_path: Path) -> None:
    result = TextExtractor().extract(tmp_path / "nao_existe.txt", AppConfig())
    assert result.status == "error"
    assert result.error


def test_html_extraction_strips_tags_and_scripts(tmp_path: Path) -> None:
    target = tmp_path / "pagina.html"
    target.write_text(
        "<html><head><script>var x = 'invisivel';</script></head>"
        "<body><h1>Título</h1><p>parágrafo visível</p></body></html>",
        encoding="utf-8",
    )
    result = HtmlExtractor().extract(target, AppConfig())
    assert result.status == "ok"
    assert "Título" in result.text
    assert "parágrafo visível" in result.text
    assert "invisivel" not in result.text
