"""Contrato comum dos extratores de conteúdo e registro por extensão.

Para adicionar suporte a um novo formato, crie uma subclasse de
:class:`BaseExtractor`, declare as extensões atendidas em ``extensions`` e
registre-a em :func:`build_registry` (``app/indexing/extractors/__init__.py``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.services.settings_service import AppConfig

# Limite defensivo do texto armazenado por arquivo (caracteres), para conter
# o tamanho do banco e o consumo de memória em arquivos muito grandes.
MAX_CONTENT_CHARS = 1_000_000


@dataclass(slots=True)
class ExtractionResult:
    """Resultado de uma extração de conteúdo."""

    text: str = ""
    status: str = "ok"  # ok | error | metadata_only
    error: Optional[str] = None

    def truncated(self) -> "ExtractionResult":
        """Retorna o resultado com o texto limitado a MAX_CONTENT_CHARS."""
        if len(self.text) > MAX_CONTENT_CHARS:
            return ExtractionResult(
                text=self.text[:MAX_CONTENT_CHARS],
                status=self.status,
                error=self.error,
            )
        return self


class BaseExtractor(ABC):
    """Extrator de conteúdo textual para um conjunto de extensões."""

    #: Extensões (minúsculas, sem ponto) atendidas por este extrator.
    extensions: tuple[str, ...] = ()

    def is_available(self) -> bool:
        """Indica se as dependências do extrator estão instaladas."""
        return True

    @abstractmethod
    def extract(self, path: Path, config: AppConfig) -> ExtractionResult:
        """Extrai o texto de ``path``. Não deve propagar exceções esperadas."""
