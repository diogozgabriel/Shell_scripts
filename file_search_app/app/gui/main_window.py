"""Janela principal: busca, filtros, resultados e controle da indexação."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from PySide6.QtCore import (
    QDate,
    QObject,
    QPoint,
    QRunnable,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import Database
from app.gui.models import COL_SNIPPET, SearchResultsModel
from app.gui.settings_dialog import SettingsDialog
from app.indexing.indexer import IndexStats
from app.indexing.scheduler import IndexScheduler
from app.search.search_service import SearchFilters, SearchService
from app.services.file_manager import FileManagerService
from app.services.settings_service import AppConfig, SettingsService

logger = logging.getLogger(__name__)

SEARCH_DEBOUNCE_MS = 300


class _SearchSignals(QObject):
    finished = Signal(int, list)  # request_id, list[SearchResult]
    failed = Signal(int, str)


class _SearchTask(QRunnable):
    """Executa uma busca no QThreadPool para não bloquear a interface."""

    def __init__(
        self,
        service: SearchService,
        request_id: int,
        query: str,
        filters: SearchFilters,
    ) -> None:
        super().__init__()
        self.signals = _SearchSignals()
        self._service = service
        self._request_id = request_id
        self._query = query
        self._filters = filters

    def run(self) -> None:
        try:
            results = self._service.search(self._query, self._filters)
            self.signals.finished.emit(self._request_id, results)
        except Exception as exc:
            logger.exception("Erro na busca")
            self.signals.failed.emit(self._request_id, str(exc))


class MainWindow(QMainWindow):
    """Janela principal do aplicativo de busca de arquivos."""

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.setWindowTitle("Busca de Arquivos")
        self.resize(1000, 640)

        self._database = database
        self._settings_service = SettingsService(database)
        self._search_service = SearchService(database)
        self._file_manager = FileManagerService()
        self._config: AppConfig = self._settings_service.load()

        self._scheduler = IndexScheduler(database, self)
        self._scheduler.indexing_started.connect(self._on_indexing_started)
        self._scheduler.indexing_progress.connect(self._on_indexing_progress)
        self._scheduler.indexing_finished.connect(self._on_indexing_finished)
        self._scheduler.indexing_failed.connect(self._on_indexing_failed)

        self._thread_pool = QThreadPool(self)
        self._thread_pool.setMaxThreadCount(1)
        self._search_request_id = 0

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._run_search)

        self._build_ui()
        self._scheduler.apply_config(self._config)
        if not self._config.folders:
            self._status_label.setText(
                "Nenhuma pasta configurada — clique em “Pastas…” para começar."
            )

    # ------------------------------------------------------------------ #
    # Interface
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)

        # Linha de busca
        search_row = QHBoxLayout()
        self.search_edit = QLineEdit(central)
        self.search_edit.setPlaceholderText("Pesquisar por nome ou conteúdo…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_query_changed)
        search_row.addWidget(self.search_edit, stretch=1)
        clear_button = QPushButton("Limpar", central)
        clear_button.clicked.connect(self.search_edit.clear)
        search_row.addWidget(clear_button)
        settings_button = QPushButton("Pastas…", central)
        settings_button.clicked.connect(self._open_settings)
        search_row.addWidget(settings_button)
        self.update_button = QPushButton("Atualizar índice agora", central)
        self.update_button.clicked.connect(self._scheduler.start_indexing)
        search_row.addWidget(self.update_button)
        self.cancel_button = QPushButton("Cancelar indexação", central)
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._scheduler.cancel_indexing)
        search_row.addWidget(self.cancel_button)
        layout.addLayout(search_row)

        # Linha de filtros
        filters_row = QHBoxLayout()
        filters_row.addWidget(QLabel("Buscar em:", central))
        self.mode_combo = QComboBox(central)
        self.mode_combo.addItem("Nome e conteúdo", "both")
        self.mode_combo.addItem("Somente nome", "name")
        self.mode_combo.addItem("Somente conteúdo", "content")
        self.mode_combo.currentIndexChanged.connect(self._on_query_changed)
        filters_row.addWidget(self.mode_combo)

        filters_row.addWidget(QLabel("Extensões:", central))
        self.extensions_edit = QLineEdit(central)
        self.extensions_edit.setPlaceholderText("pdf, txt…")
        self.extensions_edit.setMaximumWidth(120)
        self.extensions_edit.textChanged.connect(self._on_query_changed)
        filters_row.addWidget(self.extensions_edit)

        filters_row.addWidget(QLabel("Pasta:", central))
        self.folder_combo = QComboBox(central)
        self.folder_combo.currentIndexChanged.connect(self._on_query_changed)
        filters_row.addWidget(self.folder_combo, stretch=1)

        self.date_check = QCheckBox("Modificado entre", central)
        self.date_check.toggled.connect(self._on_query_changed)
        filters_row.addWidget(self.date_check)
        self.date_from_edit = QDateEdit(QDate.currentDate().addMonths(-1), central)
        self.date_from_edit.setCalendarPopup(True)
        self.date_from_edit.dateChanged.connect(self._on_query_changed)
        filters_row.addWidget(self.date_from_edit)
        self.date_to_edit = QDateEdit(QDate.currentDate(), central)
        self.date_to_edit.setCalendarPopup(True)
        self.date_to_edit.dateChanged.connect(self._on_query_changed)
        filters_row.addWidget(self.date_to_edit)

        filters_row.addWidget(QLabel("Tamanho máx.:", central))
        self.size_max_spin = QSpinBox(central)
        self.size_max_spin.setRange(0, 100_000)
        self.size_max_spin.setSpecialValueText("—")
        self.size_max_spin.setSuffix(" MB")
        self.size_max_spin.valueChanged.connect(self._on_query_changed)
        filters_row.addWidget(self.size_max_spin)
        layout.addLayout(filters_row)

        # Tabela de resultados
        self.results_model = SearchResultsModel()
        self.results_table = QTableView(central)
        self.results_table.setModel(self.results_model)
        self.results_table.setSelectionBehavior(QTableView.SelectRows)
        self.results_table.setSelectionMode(QTableView.SingleSelection)
        self.results_table.setEditTriggers(QTableView.NoEditTriggers)
        self.results_table.setSortingEnabled(False)
        self.results_table.verticalHeader().setVisible(False)
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.results_table.setColumnWidth(0, 220)
        self.results_table.setColumnWidth(1, 320)
        self.results_table.setColumnWidth(2, 50)
        self.results_table.setColumnWidth(3, 130)
        self.results_table.setColumnWidth(4, 90)
        self.results_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.results_table, stretch=1)

        # Ações rápidas
        actions_row = QHBoxLayout()
        copy_button = QPushButton("Copiar caminho", central)
        copy_button.clicked.connect(self._copy_selected_path)
        actions_row.addWidget(copy_button)
        open_folder_button = QPushButton("Abrir pasta", central)
        open_folder_button.clicked.connect(self._open_selected_folder)
        actions_row.addWidget(open_folder_button)
        reveal_button = QPushButton("Revelar no gerenciador", central)
        reveal_button.clicked.connect(self._reveal_selected)
        actions_row.addWidget(reveal_button)
        actions_row.addStretch()
        layout.addLayout(actions_row)

        self.setCentralWidget(central)

        # Barra de status
        self._status_label = QLabel("Pronto.", self)
        self.statusBar().addWidget(self._status_label, stretch=1)
        self._index_progress_label = QLabel("", self)
        self.statusBar().addPermanentWidget(self._index_progress_label)
        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 0)  # indeterminado
        self._progress_bar.setMaximumWidth(140)
        self._progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self._progress_bar)
        self._last_index_label = QLabel("Última indexação: nunca", self)
        self.statusBar().addPermanentWidget(self._last_index_label)

        self._reload_folder_filter()

    def _reload_folder_filter(self) -> None:
        current = self.folder_combo.currentData()
        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        self.folder_combo.addItem("Todas as pastas", None)
        for folder in self._config.folders:
            self.folder_combo.addItem(folder.path, folder.path)
        index = self.folder_combo.findData(current)
        self.folder_combo.setCurrentIndex(index if index >= 0 else 0)
        self.folder_combo.blockSignals(False)

    # ------------------------------------------------------------------ #
    # Busca
    # ------------------------------------------------------------------ #

    @Slot()
    def _on_query_changed(self) -> None:
        self._debounce_timer.start()

    def _current_filters(self) -> SearchFilters:
        filters = SearchFilters(mode=str(self.mode_combo.currentData()))
        filters.extensions = [
            e.strip().lower().lstrip(".")
            for e in self.extensions_edit.text().split(",")
            if e.strip()
        ]
        filters.folder = self.folder_combo.currentData()
        if self.date_check.isChecked():
            date_from = self.date_from_edit.date()
            date_to = self.date_to_edit.date().addDays(1)
            filters.date_from = datetime(
                date_from.year(), date_from.month(), date_from.day()
            ).timestamp()
            filters.date_to = datetime(
                date_to.year(), date_to.month(), date_to.day()
            ).timestamp()
        if self.size_max_spin.value() > 0:
            filters.size_max = self.size_max_spin.value() * 1024 * 1024
        return filters

    @Slot()
    def _run_search(self) -> None:
        query = self.search_edit.text().strip()
        self._search_request_id += 1
        if not query:
            self.results_model.set_results([])
            self._status_label.setText("Pronto.")
            return
        task = _SearchTask(
            self._search_service,
            self._search_request_id,
            query,
            self._current_filters(),
        )
        task.signals.finished.connect(self._on_search_finished)
        task.signals.failed.connect(self._on_search_failed)
        self._thread_pool.start(task)

    @Slot(int, list)
    def _on_search_finished(self, request_id: int, results: list) -> None:
        if request_id != self._search_request_id:
            return  # resultado obsoleto: o usuário já digitou outra coisa
        self.results_model.set_results(results)
        self._status_label.setText(f"{len(results)} resultado(s).")

    @Slot(int, str)
    def _on_search_failed(self, request_id: int, message: str) -> None:
        if request_id != self._search_request_id:
            return
        self._status_label.setText(f"Erro na busca: {message}")

    # ------------------------------------------------------------------ #
    # Indexação
    # ------------------------------------------------------------------ #

    @Slot()
    def _on_indexing_started(self) -> None:
        self.update_button.setEnabled(False)
        self.cancel_button.setVisible(True)
        self._progress_bar.setVisible(True)
        self._index_progress_label.setText("Indexando…")

    @Slot(str)
    def _on_indexing_progress(self, filename: str) -> None:
        self._index_progress_label.setText(f"Indexando: {filename[:48]}")

    @Slot(object)
    def _on_indexing_finished(self, stats: IndexStats) -> None:
        self.update_button.setEnabled(True)
        self.cancel_button.setVisible(False)
        self._progress_bar.setVisible(False)
        self._index_progress_label.setText("")
        self._status_label.setText(f"Indexação: {stats.summary()}")
        if self._scheduler.last_index_time is not None:
            when = datetime.fromtimestamp(self._scheduler.last_index_time)
            self._last_index_label.setText(
                f"Última indexação: {when.strftime('%d/%m/%Y %H:%M')}"
            )
        if self.search_edit.text().strip():
            self._run_search()

    @Slot(str)
    def _on_indexing_failed(self, message: str) -> None:
        self.update_button.setEnabled(True)
        self.cancel_button.setVisible(False)
        self._progress_bar.setVisible(False)
        self._index_progress_label.setText("")
        self._status_label.setText(message)

    # ------------------------------------------------------------------ #
    # Configurações
    # ------------------------------------------------------------------ #

    @Slot()
    def _open_settings(self) -> None:
        dialog = SettingsDialog(self._config, self)
        if dialog.exec() != SettingsDialog.Accepted:
            return
        had_folders = bool(self._config.folders)
        self._config = dialog.result_config()
        try:
            self._settings_service.save(self._config)
        except Exception as exc:
            logger.exception("Falha ao salvar configurações")
            QMessageBox.critical(self, "Erro", f"Falha ao salvar: {exc}")
            return
        self._scheduler.apply_config(self._config)
        self._reload_folder_filter()
        if self._config.folders and not had_folders:
            self._scheduler.start_indexing()

    # ------------------------------------------------------------------ #
    # Ações sobre resultados
    # ------------------------------------------------------------------ #

    def _selected_result(self):
        indexes = self.results_table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self.results_model.result_at(indexes[0].row())

    @Slot()
    def _copy_selected_path(self) -> None:
        result = self._selected_result()
        if result is not None:
            self._file_manager.copy_path_to_clipboard(result.path)
            self._status_label.setText("Caminho copiado.")

    @Slot()
    def _open_selected_folder(self) -> None:
        result = self._selected_result()
        if result is not None:
            self._file_manager.open_containing_folder(result.path)

    @Slot()
    def _reveal_selected(self) -> None:
        result = self._selected_result()
        if result is not None:
            self._file_manager.reveal_file(result.path)

    @Slot(QPoint)
    def _show_context_menu(self, position: QPoint) -> None:
        result = self._selected_result()
        if result is None:
            return
        menu = QMenu(self)
        copy_action = QAction("Copiar caminho", menu)
        copy_action.triggered.connect(self._copy_selected_path)
        menu.addAction(copy_action)
        open_action = QAction("Abrir pasta que contém o arquivo", menu)
        open_action.triggered.connect(self._open_selected_folder)
        menu.addAction(open_action)
        reveal_action = QAction("Revelar no gerenciador de arquivos", menu)
        reveal_action.triggered.connect(self._reveal_selected)
        menu.addAction(reveal_action)
        menu.exec(self.results_table.viewport().mapToGlobal(position))

    # ------------------------------------------------------------------ #

    def closeEvent(self, event) -> None:  # noqa: N802 (API Qt)
        self._scheduler.shutdown()
        self._thread_pool.waitForDone(3000)
        super().closeEvent(event)
