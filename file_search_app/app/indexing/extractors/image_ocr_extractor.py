"""OCR de imagens via Tesseract (pytesseract + Pillow).

Também expõe utilitários de OCR reutilizados pelo extrator de PDF
(detecção do Tesseract, instruções de instalação e OCR de imagens em bytes).
"""

from __future__ import annotations

import io
import logging
import shutil
from pathlib import Path

from app.indexing.extractors.base import BaseExtractor, ExtractionResult
from app.services.settings_service import AppConfig

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image

    _OCR_IMPORTS_OK = True
except ImportError:
    _OCR_IMPORTS_OK = False

TESSERACT_INSTALL_INSTRUCTIONS = (
    "Tesseract OCR não encontrado.\n\n"
    "Instalação:\n"
    "  • Garuda/Arch:   sudo pacman -S tesseract tesseract-data-por tesseract-data-eng\n"
    "  • Debian/Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-por\n"
    "  • Fedora:        sudo dnf install tesseract tesseract-langpack-por\n"
    "  • Windows:       instalador em https://github.com/UB-Mannheim/tesseract/wiki\n"
    "  • macOS:         brew install tesseract tesseract-lang"
)


def is_tesseract_available() -> bool:
    """Verifica se o binário do Tesseract e as bibliotecas Python existem."""
    return _OCR_IMPORTS_OK and shutil.which("tesseract") is not None


def ocr_image_bytes(data: bytes, language: str) -> str:
    """Aplica OCR a uma imagem em memória. Propaga exceções do Tesseract."""
    with Image.open(io.BytesIO(data)) as image:
        return pytesseract.image_to_string(image, lang=language)


class ImageOcrExtractor(BaseExtractor):
    """Extrai texto de imagens por OCR quando o recurso está ativado."""

    extensions = ("png", "jpg", "jpeg", "tiff", "tif", "bmp")

    def is_available(self) -> bool:
        return _OCR_IMPORTS_OK

    def extract(self, path: Path, config: AppConfig) -> ExtractionResult:
        ocr = config.ocr
        extension = path.suffix.lower().lstrip(".")
        if not ocr.enabled or extension not in ocr.formats:
            return ExtractionResult(status="metadata_only")
        if path.stat().st_size > ocr.max_file_size_mb * 1024 * 1024:
            return ExtractionResult(
                status="metadata_only",
                error="Imagem acima do limite de tamanho para OCR",
            )
        if not is_tesseract_available():
            return ExtractionResult(
                status="metadata_only", error=TESSERACT_INSTALL_INSTRUCTIONS
            )
        try:
            with Image.open(path) as image:
                text = pytesseract.image_to_string(image, lang=ocr.language)
            return ExtractionResult(text=text.strip()).truncated()
        except Exception as exc:  # falha de OCR não interrompe a indexação
            logger.warning("OCR falhou em %s: %s", path, exc)
            return ExtractionResult(status="error", error=f"OCR falhou: {exc}")
