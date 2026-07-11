"""Extração de texto de PDFs com PyMuPDF e OCR opcional de páginas digitalizadas."""

from __future__ import annotations

import logging
from pathlib import Path

from app.indexing.extractors.base import BaseExtractor, ExtractionResult
from app.indexing.extractors.image_ocr_extractor import (
    is_tesseract_available,
    ocr_image_bytes,
)
from app.services.settings_service import AppConfig

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF

    _PYMUPDF_OK = True
except ImportError:
    _PYMUPDF_OK = False

# Uma página com menos caracteres que isto é tratada como digitalizada
# (candidata a OCR) quando o OCR está habilitado.
_MIN_CHARS_PER_PAGE = 20
_OCR_RENDER_DPI = 200


class PdfExtractor(BaseExtractor):
    """Extrai texto nativo de PDFs; aplica OCR apenas em páginas sem texto."""

    extensions = ("pdf",)

    def is_available(self) -> bool:
        return _PYMUPDF_OK

    def extract(self, path: Path, config: AppConfig) -> ExtractionResult:
        if not _PYMUPDF_OK:
            return ExtractionResult(
                status="metadata_only",
                error="PyMuPDF não instalado (pip install PyMuPDF)",
            )
        try:
            return self._extract(path, config).truncated()
        except Exception as exc:  # PDF corrompido/cifrado não para a indexação
            logger.warning("Falha ao ler PDF %s: %s", path, exc)
            return ExtractionResult(status="error", error=f"PDF ilegível: {exc}")

    def _extract(self, path: Path, config: AppConfig) -> ExtractionResult:
        ocr = config.ocr
        ocr_wanted = (
            ocr.enabled
            and "pdf" in ocr.formats
            and path.stat().st_size <= ocr.max_file_size_mb * 1024 * 1024
        )
        ocr_possible = ocr_wanted and is_tesseract_available()
        ocr_error: str | None = None
        if ocr_wanted and not ocr_possible:
            ocr_error = "OCR indisponível: Tesseract não instalado"

        pages_text: list[str] = []
        ocr_pages_done = 0
        with fitz.open(path) as document:
            for page in document:
                text = page.get_text().strip()
                if (
                    len(text) < _MIN_CHARS_PER_PAGE
                    and ocr_possible
                    and ocr_pages_done < ocr.max_pdf_pages
                ):
                    try:
                        pixmap = page.get_pixmap(dpi=_OCR_RENDER_DPI)
                        text = ocr_image_bytes(
                            pixmap.tobytes("png"), ocr.language
                        ).strip()
                        ocr_pages_done += 1
                    except Exception as exc:
                        ocr_error = f"OCR falhou na página {page.number + 1}: {exc}"
                        logger.warning("%s (%s)", ocr_error, path)
                if text:
                    pages_text.append(text)

        return ExtractionResult(text="\n".join(pages_text), error=ocr_error)
