"""Modelo Qt (QAbstractTableModel) para a tabela de resultados da busca."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from app.search.search_service import SearchResult

COLUMNS = ("Nome", "Caminho", "Ext", "Modificado", "Tamanho", "Trecho")
COL_NAME, COL_PATH, COL_EXT, COL_MTIME, COL_SIZE, COL_SNIPPET = range(6)


def format_size(size: int) -> str:
    """Formata bytes em unidades legíveis (KB, MB, GB)."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(size)} B"


class SearchResultsModel(QAbstractTableModel):
    """Expõe uma lista de :class:`SearchResult` para um ``QTableView``."""

    def __init__(self) -> None:
        super().__init__()
        self._results: list[SearchResult] = []

    def set_results(self, results: list[SearchResult]) -> None:
        self.beginResetModel()
        self._results = results
        self.endResetModel()

    def result_at(self, row: int) -> Optional[SearchResult]:
        if 0 <= row < len(self._results):
            return self._results[row]
        return None

    # ------------------------------------------------------------------ #
    # API do QAbstractTableModel
    # ------------------------------------------------------------------ #

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._results)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        result = self._results[index.row()]
        column = index.column()
        if role in (Qt.DisplayRole, Qt.ToolTipRole):
            if column == COL_NAME:
                return result.name
            if column == COL_PATH:
                return result.path
            if column == COL_EXT:
                return result.extension
            if column == COL_MTIME:
                return datetime.fromtimestamp(result.mtime).strftime(
                    "%d/%m/%Y %H:%M"
                )
            if column == COL_SIZE:
                return format_size(result.size)
            if column == COL_SNIPPET:
                snippet = result.snippet.replace("\n", " ")
                return snippet if role == Qt.ToolTipRole else snippet[:200]
        return None
