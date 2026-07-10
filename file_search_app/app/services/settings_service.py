"""Modelo de configuração da aplicação e sua persistência no banco.

As configurações são serializadas em JSON na tabela ``settings``, o que as
mantém junto do índice e simplifica backup/reset.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from app.database.connection import Database
from app.database.repository import SettingsRepository

logger = logging.getLogger(__name__)

CONFIG_KEY = "app_config"

DEFAULT_EXCLUDED_DIRS = [
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".cache",
    ".venv",
    "venv",
    ".Trash",
    "Trash",
    ".local/share/Trash",
    ".thumbnails",
]

DEFAULT_EXCLUDED_PATTERNS = ["*.tmp", "*.temp", "*.swp", "*.part", "*~", "*.pyc"]

OCR_SUPPORTED_FORMATS = ["png", "jpg", "jpeg", "tiff", "bmp", "pdf"]


@dataclass(slots=True)
class IndexedFolder:
    """Pasta selecionada para indexação."""

    path: str
    recursive: bool = True


@dataclass(slots=True)
class OcrConfig:
    """Configuração de OCR (desativado por padrão)."""

    enabled: bool = False
    language: str = "por+eng"
    max_pdf_pages: int = 10
    max_file_size_mb: int = 20
    formats: list[str] = field(default_factory=lambda: list(OCR_SUPPORTED_FORMATS))


@dataclass(slots=True)
class AppConfig:
    """Configuração completa da aplicação."""

    folders: list[IndexedFolder] = field(default_factory=list)
    excluded_dirs: list[str] = field(
        default_factory=lambda: list(DEFAULT_EXCLUDED_DIRS)
    )
    excluded_extensions: list[str] = field(default_factory=list)
    excluded_patterns: list[str] = field(
        default_factory=lambda: list(DEFAULT_EXCLUDED_PATTERNS)
    )
    max_file_size_mb: int = 50
    auto_update_enabled: bool = True
    auto_update_interval_minutes: int = 20
    ocr: OcrConfig = field(default_factory=OcrConfig)

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "AppConfig":
        """Reconstrói a configuração a partir do JSON, tolerando chaves extras."""
        config = AppConfig()
        config.folders = [
            IndexedFolder(path=f.get("path", ""), recursive=bool(f.get("recursive", True)))
            for f in data.get("folders", [])
            if f.get("path")
        ]
        config.excluded_dirs = list(data.get("excluded_dirs", config.excluded_dirs))
        config.excluded_extensions = [
            e.lower().lstrip(".") for e in data.get("excluded_extensions", [])
        ]
        config.excluded_patterns = list(
            data.get("excluded_patterns", config.excluded_patterns)
        )
        config.max_file_size_mb = int(data.get("max_file_size_mb", 50))
        config.auto_update_enabled = bool(data.get("auto_update_enabled", True))
        config.auto_update_interval_minutes = max(
            1, int(data.get("auto_update_interval_minutes", 20))
        )
        ocr_data = data.get("ocr", {})
        config.ocr = OcrConfig(
            enabled=bool(ocr_data.get("enabled", False)),
            language=str(ocr_data.get("language", "por+eng")),
            max_pdf_pages=max(1, int(ocr_data.get("max_pdf_pages", 10))),
            max_file_size_mb=max(1, int(ocr_data.get("max_file_size_mb", 20))),
            formats=[
                f for f in ocr_data.get("formats", OCR_SUPPORTED_FORMATS)
                if f in OCR_SUPPORTED_FORMATS
            ],
        )
        return config


class SettingsService:
    """Carrega e salva :class:`AppConfig` usando o banco da aplicação."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def load(self) -> AppConfig:
        """Lê a configuração persistida; retorna padrões se ausente/corrompida."""
        conn = self._database.connect()
        try:
            raw = SettingsRepository(conn).get(CONFIG_KEY)
        finally:
            conn.close()
        if raw is None:
            return AppConfig()
        try:
            return AppConfig.from_dict(json.loads(raw))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.error("Configuração inválida no banco (%s); usando padrões.", exc)
            return AppConfig()

    def save(self, config: AppConfig) -> None:
        """Serializa e grava a configuração."""
        conn = self._database.connect()
        try:
            SettingsRepository(conn).set(CONFIG_KEY, json.dumps(asdict(config)))
        finally:
            conn.close()
