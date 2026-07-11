"""Extrator para formatos de texto puro (TXT, MD, CSV, JSON, XML, HTML...)."""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from pathlib import Path

from app.indexing.extractors.base import (
    MAX_CONTENT_CHARS,
    BaseExtractor,
    ExtractionResult,
)
from app.services.settings_service import AppConfig

logger = logging.getLogger(__name__)

_ENCODINGS = ("utf-8", "latin-1")


class _HTMLTextParser(HTMLParser):
    """Extrai apenas o texto visível de um documento HTML."""

    _IGNORED_TAGS = {"script", "style"}

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._IGNORED_TAGS:
            self._ignore_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._IGNORED_TAGS and self._ignore_depth > 0:
            self._ignore_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignore_depth == 0 and data.strip():
            self._chunks.append(data)

    def text(self) -> str:
        return " ".join(self._chunks)


def _read_text(path: Path) -> str:
    """Lê texto tentando UTF-8 e caindo para Latin-1 (nunca falha por encoding)."""
    raw = path.read_bytes()[: MAX_CONTENT_CHARS * 4]
    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class TextExtractor(BaseExtractor):
    """Lê o conteúdo de arquivos de texto simples."""

    extensions = ("txt", "md", "csv", "json", "xml", "log", "ini", "conf",
                  "yaml", "yml", "sh", "py")

    def extract(self, path: Path, config: AppConfig) -> ExtractionResult:
        try:
            return ExtractionResult(text=_read_text(path)).truncated()
        except OSError as exc:
            return ExtractionResult(status="error", error=str(exc))


class HtmlExtractor(BaseExtractor):
    """Extrai o texto visível de arquivos HTML."""

    extensions = ("html", "htm", "xhtml")

    def extract(self, path: Path, config: AppConfig) -> ExtractionResult:
        try:
            parser = _HTMLTextParser()
            parser.feed(_read_text(path))
            text = re.sub(r"\s+", " ", parser.text())
            return ExtractionResult(text=text).truncated()
        except OSError as exc:
            return ExtractionResult(status="error", error=str(exc))
        except Exception as exc:  # HTML malformado não deve parar a indexação
            logger.debug("HTML malformado em %s: %s", path, exc)
            return ExtractionResult(status="error", error=f"HTML inválido: {exc}")
