"""Execução da indexação em segundo plano e atualização automática.

:class:`IndexScheduler` roda o :class:`~app.indexing.indexer.Indexer` em uma
``QThread`` dedicada, impede execuções simultâneas, oferece cancelamento
cooperativo e dispara execuções periódicas via ``QTimer`` conforme a
configuração de atualização automática.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from app.database.connection import Database
from app.indexing.indexer import Indexer, IndexStats
from app.services.settings_service import AppConfig

logger = logging.getLogger(__name__)


class _IndexWorker(QObject):
    """Executa uma indexação completa dentro de uma QThread."""

    progress = Signal(str)
    finished = Signal(object)  # IndexStats
    failed = Signal(str)

    def __init__(
        self, database: Database, config: AppConfig, cancel: threading.Event
    ) -> None:
        super().__init__()
        self._database = database
        self._config = config
        self._cancel = cancel

    @Slot()
    def run(self) -> None:
        try:
            indexer = Indexer(self._database, self._config)
            stats = indexer.run(cancel=self._cancel, progress=self.progress.emit)
            self.finished.emit(stats)
        except Exception as exc:  # erro inesperado não pode derrubar a GUI
            logger.exception("Erro inesperado na indexação")
            self.failed.emit(str(exc))


class IndexScheduler(QObject):
    """Coordena indexações manuais e automáticas sem bloquear a interface."""

    indexing_started = Signal()
    indexing_progress = Signal(str)
    indexing_finished = Signal(object)  # IndexStats
    indexing_failed = Signal(str)

    def __init__(self, database: Database, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._database = database
        self._config = AppConfig()
        self._thread: Optional[QThread] = None
        self._worker: Optional[_IndexWorker] = None
        self._cancel = threading.Event()
        self.last_index_time: Optional[float] = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.start_indexing)

    # ------------------------------------------------------------------ #

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def apply_config(self, config: AppConfig) -> None:
        """Atualiza a configuração e o timer de atualização automática."""
        self._config = config
        self._timer.stop()
        if config.auto_update_enabled and config.folders:
            self._timer.start(config.auto_update_interval_minutes * 60 * 1000)

    @Slot()
    def start_indexing(self) -> None:
        """Inicia uma indexação, ignorando o pedido se já houver uma em curso."""
        if self.is_running:
            logger.info("Indexação já em andamento; novo pedido ignorado.")
            return
        if not self._config.folders:
            self.indexing_failed.emit(
                "Nenhuma pasta configurada. Use o botão “Pastas…”."
            )
            return

        self._cancel = threading.Event()
        self._thread = QThread(self)
        self._worker = _IndexWorker(self._database, self._config, self._cancel)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.indexing_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)
        self._thread.start()
        self.indexing_started.emit()

    @Slot()
    def cancel_indexing(self) -> None:
        """Solicita cancelamento cooperativo da indexação atual."""
        if self.is_running:
            self._cancel.set()

    def shutdown(self) -> None:
        """Cancela e aguarda a thread de indexação ao encerrar a aplicação."""
        self._timer.stop()
        if self._thread is not None:
            self._cancel.set()
            self._thread.quit()
            self._thread.wait(10_000)

    # ------------------------------------------------------------------ #

    @Slot(object)
    def _on_finished(self, stats: IndexStats) -> None:
        if not stats.cancelled:
            self.last_index_time = time.time()
        self.indexing_finished.emit(stats)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.indexing_failed.emit(message)

    @Slot()
    def _cleanup(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
