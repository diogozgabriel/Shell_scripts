"""Indexador incremental de arquivos.

Percorre as pastas configuradas, extrai conteúdo com os extratores
registrados e mantém o banco sincronizado com o disco:

* arquivos novos são inseridos;
* arquivos modificados (mtime ou tamanho diferentes) são reprocessados;
* arquivos inalterados são pulados;
* registros de arquivos removidos do disco são apagados do índice.

O indexador é independente de Qt: recebe um ``threading.Event`` para
cancelamento cooperativo e um callback de progresso, o que permite testá-lo
sem interface gráfica.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Optional

from app.database.connection import Database
from app.database.repository import (
    STATUS_METADATA_ONLY,
    FileRecord,
    FileRepository,
)
from app.indexing.extractors import build_registry
from app.indexing.extractors.base import BaseExtractor
from app.services.settings_service import AppConfig, IndexedFolder

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]

_TEMP_SUFFIXES = (".tmp", ".temp", ".swp", ".swo", ".part", ".crdownload", "~")


@dataclass(slots=True)
class IndexStats:
    """Resumo de uma execução de indexação."""

    added: int = 0
    updated: int = 0
    removed: int = 0
    skipped: int = 0
    errors: int = 0
    cancelled: bool = False
    duration_seconds: float = 0.0
    error_messages: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = (
            f"{self.added} novos, {self.updated} atualizados, "
            f"{self.removed} removidos, {self.skipped} inalterados, "
            f"{self.errors} erros em {self.duration_seconds:.1f}s"
        )
        return ("Cancelado: " if self.cancelled else "") + parts


class Indexer:
    """Executa uma varredura completa (incremental) das pastas configuradas."""

    def __init__(
        self,
        database: Database,
        config: AppConfig,
        registry: Optional[dict[str, BaseExtractor]] = None,
    ) -> None:
        self._database = database
        self._config = config
        self._registry = registry if registry is not None else build_registry()

    # ------------------------------------------------------------------ #
    # Filtros de exclusão
    # ------------------------------------------------------------------ #

    def _is_dir_excluded(self, name: str, full_path: str) -> bool:
        if name.startswith("."):
            return True
        config = self._config
        if name in config.excluded_dirs:
            return True
        return any(
            fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(full_path, pattern)
            for pattern in config.excluded_patterns
        )

    def _is_file_excluded(self, name: str, full_path: str) -> bool:
        if name.startswith(".") or name.endswith(_TEMP_SUFFIXES):
            return True
        config = self._config
        extension = Path(name).suffix.lower().lstrip(".")
        if extension in config.excluded_extensions:
            return True
        return any(
            fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(full_path, pattern)
            for pattern in config.excluded_patterns
        )

    # ------------------------------------------------------------------ #
    # Varredura
    # ------------------------------------------------------------------ #

    def _iter_folder(
        self, folder: IndexedFolder, cancel: threading.Event
    ) -> Iterator[str]:
        """Gera caminhos de arquivos candidatos dentro de uma pasta raiz.

        ``followlinks=False`` evita ciclos causados por links simbólicos.
        """
        root = Path(folder.path)
        if folder.recursive:
            for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
                if cancel.is_set():
                    return
                dirnames[:] = [
                    d
                    for d in dirnames
                    if not self._is_dir_excluded(d, os.path.join(dirpath, d))
                ]
                for filename in filenames:
                    full = os.path.join(dirpath, filename)
                    if not self._is_file_excluded(filename, full):
                        yield full
        else:
            try:
                entries = list(os.scandir(root))
            except OSError as exc:
                logger.warning("Não foi possível listar %s: %s", root, exc)
                return
            for entry in entries:
                if cancel.is_set():
                    return
                try:
                    is_file = entry.is_file(follow_symlinks=False)
                except OSError:
                    continue
                if is_file and not self._is_file_excluded(entry.name, entry.path):
                    yield entry.path

    # ------------------------------------------------------------------ #
    # Execução
    # ------------------------------------------------------------------ #

    def run(
        self,
        cancel: Optional[threading.Event] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> IndexStats:
        """Executa a indexação; segura para chamar fora da thread principal."""
        cancel = cancel or threading.Event()
        stats = IndexStats()
        started = time.monotonic()
        conn = self._database.connect()
        try:
            repository = FileRepository(conn)
            signatures = repository.get_all_signatures()
            seen: set[str] = set()
            scanned_roots: list[str] = []

            for folder in self._config.folders:
                root = Path(folder.path)
                if not root.is_dir():
                    logger.warning("Pasta configurada inacessível: %s", root)
                    continue
                scanned_roots.append(str(root))
                for file_path in self._iter_folder(folder, cancel):
                    if cancel.is_set():
                        break
                    self._process_file(
                        file_path, repository, signatures, seen, stats, progress
                    )
                if cancel.is_set():
                    break

            if cancel.is_set():
                stats.cancelled = True
            else:
                stats.removed = self._remove_stale(
                    repository, signatures, seen, scanned_roots
                )
                if stats.added or stats.updated or stats.removed:
                    repository.optimize_fts()
        finally:
            conn.close()
        stats.duration_seconds = time.monotonic() - started
        logger.info("Indexação concluída: %s", stats.summary())
        return stats

    def _process_file(
        self,
        file_path: str,
        repository: FileRepository,
        signatures: dict[str, tuple[int, float, str]],
        seen: set[str],
        stats: IndexStats,
        progress: Optional[ProgressCallback],
    ) -> None:
        """Indexa um único arquivo, registrando erros sem interromper o processo."""
        seen.add(file_path)
        path = Path(file_path)
        try:
            stat_result = path.stat()
        except OSError as exc:
            # Sem stat não há como indexar; se já estava no índice e sumiu,
            # a remoção de obsoletos cuidará dele.
            logger.warning("Sem acesso a %s: %s", file_path, exc)
            stats.errors += 1
            stats.error_messages.append(f"{file_path}: {exc}")
            return

        size = stat_result.st_size
        mtime = stat_result.st_mtime
        known = signatures.get(file_path)
        if known is not None and known[0] == size and known[1] == mtime:
            stats.skipped += 1
            return

        if progress is not None:
            progress(path.name)

        record = FileRecord(
            path=file_path,
            name=path.name,
            extension=path.suffix.lower().lstrip("."),
            size=size,
            mtime=mtime,
        )

        if size > self._config.max_file_size_bytes:
            record.status = STATUS_METADATA_ONLY
            record.error = "Arquivo acima do limite de tamanho configurado"
        else:
            extractor = self._registry.get(record.extension)
            if extractor is None:
                record.status = STATUS_METADATA_ONLY
            else:
                try:
                    result = extractor.extract(path, self._config)
                except Exception as exc:  # defesa extra: extrator com bug
                    logger.exception("Extrator falhou em %s", file_path)
                    result = None
                    record.status = "error"
                    record.error = str(exc)
                if result is not None:
                    record.content = result.text
                    record.status = result.status
                    record.error = result.error

        try:
            repository.upsert(record)
        except Exception as exc:
            logger.exception("Falha ao gravar %s no índice", file_path)
            stats.errors += 1
            stats.error_messages.append(f"{file_path}: {exc}")
            return

        if record.status == "error":
            stats.errors += 1
            if record.error:
                stats.error_messages.append(f"{file_path}: {record.error}")
        if known is None:
            stats.added += 1
        else:
            stats.updated += 1

    def _remove_stale(
        self,
        repository: FileRepository,
        signatures: dict[str, tuple[int, float, str]],
        seen: set[str],
        scanned_roots: list[str],
    ) -> int:
        """Remove do índice registros de arquivos que não existem mais.

        Remove entradas não vistas que estejam sob uma raiz varrida com
        sucesso, e entradas fora de qualquer raiz configurada (pasta removida
        das configurações). Raízes inacessíveis nesta execução são preservadas.
        """
        configured_roots = [str(Path(f.path)) for f in self._config.folders]
        stale: list[str] = []
        for known_path in signatures:
            if known_path in seen:
                continue
            under_scanned = any(
                known_path.startswith(root.rstrip(os.sep) + os.sep)
                for root in scanned_roots
            )
            under_configured = any(
                known_path.startswith(root.rstrip(os.sep) + os.sep)
                for root in configured_roots
            )
            if under_scanned or not under_configured:
                stale.append(known_path)
        return repository.delete_paths(stale) if stale else 0
