"""Registro dos extratores disponíveis, indexado por extensão."""

from __future__ import annotations

from app.indexing.extractors.base import BaseExtractor, ExtractionResult
from app.indexing.extractors.image_ocr_extractor import ImageOcrExtractor
from app.indexing.extractors.office_extractor import DocxExtractor, XlsxExtractor
from app.indexing.extractors.pdf_extractor import PdfExtractor
from app.indexing.extractors.text_extractor import HtmlExtractor, TextExtractor

__all__ = ["BaseExtractor", "ExtractionResult", "build_registry"]


def build_registry() -> dict[str, BaseExtractor]:
    """Cria o mapa extensão -> extrator.

    Para suportar um novo formato, acrescente a classe do extrator à lista
    abaixo; as extensões declaradas nela passam a ser atendidas.
    """
    extractors: list[BaseExtractor] = [
        TextExtractor(),
        HtmlExtractor(),
        PdfExtractor(),
        DocxExtractor(),
        XlsxExtractor(),
        ImageOcrExtractor(),
    ]
    registry: dict[str, BaseExtractor] = {}
    for extractor in extractors:
        for extension in extractor.extensions:
            registry[extension] = extractor
    return registry
