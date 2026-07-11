"""Diálogo de configurações: pastas, exclusões, atualização automática e OCR."""

from __future__ import annotations

import copy
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.indexing.extractors.image_ocr_extractor import (
    TESSERACT_INSTALL_INSTRUCTIONS,
    is_tesseract_available,
)
from app.services.settings_service import (
    OCR_SUPPORTED_FORMATS,
    AppConfig,
    IndexedFolder,
)


class SettingsDialog(QDialog):
    """Edita uma cópia de :class:`AppConfig`; retorna via :meth:`result_config`."""

    def __init__(self, config: AppConfig, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.setMinimumWidth(560)
        self._config = copy.deepcopy(config)
        self._build_ui()
        self._load_config()

    # ------------------------------------------------------------------ #
    # Construção da interface
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        folders_group = QGroupBox("Pastas indexadas", self)
        folders_layout = QVBoxLayout(folders_group)
        hint = QLabel(
            "Marque a caixa de uma pasta para indexá-la recursivamente "
            "(subpastas incluídas)."
        )
        hint.setWordWrap(True)
        folders_layout.addWidget(hint)
        self.folders_list = QListWidget(folders_group)
        folders_layout.addWidget(self.folders_list)
        buttons_row = QHBoxLayout()
        add_button = QPushButton("Adicionar pasta…", folders_group)
        add_button.clicked.connect(self._add_folder)
        remove_button = QPushButton("Remover selecionada", folders_group)
        remove_button.clicked.connect(self._remove_folder)
        buttons_row.addWidget(add_button)
        buttons_row.addWidget(remove_button)
        buttons_row.addStretch()
        folders_layout.addLayout(buttons_row)
        layout.addWidget(folders_group)

        exclusions_group = QGroupBox("Exclusões", self)
        exclusions_form = QFormLayout(exclusions_group)
        self.excluded_extensions_edit = QLineEdit(exclusions_group)
        self.excluded_extensions_edit.setPlaceholderText("ex.: iso, mkv, zip")
        exclusions_form.addRow("Extensões ignoradas:", self.excluded_extensions_edit)
        self.excluded_patterns_edit = QPlainTextEdit(exclusions_group)
        self.excluded_patterns_edit.setPlaceholderText(
            "Um padrão glob por linha, ex.: *.bak ou */Downloads/*"
        )
        self.excluded_patterns_edit.setMaximumHeight(80)
        exclusions_form.addRow("Padrões ignorados:", self.excluded_patterns_edit)
        self.max_size_spin = QSpinBox(exclusions_group)
        self.max_size_spin.setRange(1, 10_000)
        self.max_size_spin.setSuffix(" MB")
        exclusions_form.addRow("Tamanho máximo de arquivo:", self.max_size_spin)
        layout.addWidget(exclusions_group)

        update_group = QGroupBox("Atualização automática", self)
        update_form = QFormLayout(update_group)
        self.auto_update_check = QCheckBox("Atualizar o índice automaticamente")
        update_form.addRow(self.auto_update_check)
        self.interval_spin = QSpinBox(update_group)
        self.interval_spin.setRange(1, 24 * 60)
        self.interval_spin.setSuffix(" min")
        update_form.addRow("Intervalo:", self.interval_spin)
        layout.addWidget(update_group)

        ocr_group = QGroupBox("OCR (Tesseract)", self)
        ocr_form = QFormLayout(ocr_group)
        self.ocr_enabled_check = QCheckBox(
            "Ativar OCR para imagens e PDFs digitalizados (mais lento)"
        )
        ocr_form.addRow(self.ocr_enabled_check)
        self.ocr_language_combo = QComboBox(ocr_group)
        self.ocr_language_combo.setEditable(True)
        self.ocr_language_combo.addItems(["por+eng", "por", "eng", "spa", "deu", "fra"])
        ocr_form.addRow("Idioma (códigos Tesseract):", self.ocr_language_combo)
        self.ocr_max_pages_spin = QSpinBox(ocr_group)
        self.ocr_max_pages_spin.setRange(1, 500)
        ocr_form.addRow("Máx. páginas OCR por PDF:", self.ocr_max_pages_spin)
        self.ocr_max_size_spin = QSpinBox(ocr_group)
        self.ocr_max_size_spin.setRange(1, 2_000)
        self.ocr_max_size_spin.setSuffix(" MB")
        ocr_form.addRow("Tamanho máx. para OCR:", self.ocr_max_size_spin)
        self.ocr_format_checks: dict[str, QCheckBox] = {}
        formats_row = QHBoxLayout()
        for fmt in OCR_SUPPORTED_FORMATS:
            check = QCheckBox(fmt.upper(), ocr_group)
            self.ocr_format_checks[fmt] = check
            formats_row.addWidget(check)
        formats_widget = QWidget(ocr_group)
        formats_widget.setLayout(formats_row)
        ocr_form.addRow("Formatos com OCR:", formats_widget)
        layout.addWidget(ocr_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------ #
    # Carregamento e coleta
    # ------------------------------------------------------------------ #

    def _load_config(self) -> None:
        config = self._config
        for folder in config.folders:
            self._append_folder_item(folder)
        self.excluded_extensions_edit.setText(", ".join(config.excluded_extensions))
        self.excluded_patterns_edit.setPlainText("\n".join(config.excluded_patterns))
        self.max_size_spin.setValue(config.max_file_size_mb)
        self.auto_update_check.setChecked(config.auto_update_enabled)
        self.interval_spin.setValue(config.auto_update_interval_minutes)
        self.ocr_enabled_check.setChecked(config.ocr.enabled)
        self.ocr_language_combo.setCurrentText(config.ocr.language)
        self.ocr_max_pages_spin.setValue(config.ocr.max_pdf_pages)
        self.ocr_max_size_spin.setValue(config.ocr.max_file_size_mb)
        for fmt, check in self.ocr_format_checks.items():
            check.setChecked(fmt in config.ocr.formats)

    def _append_folder_item(self, folder: IndexedFolder) -> None:
        item = QListWidgetItem(folder.path, self.folders_list)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if folder.recursive else Qt.Unchecked)

    def _add_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Selecionar pasta")
        if not path:
            return
        existing = {
            self.folders_list.item(i).text()
            for i in range(self.folders_list.count())
        }
        if path in existing:
            return
        self._append_folder_item(IndexedFolder(path=path, recursive=True))

    def _remove_folder(self) -> None:
        for item in self.folders_list.selectedItems():
            self.folders_list.takeItem(self.folders_list.row(item))

    def _on_accept(self) -> None:
        config = self._config
        config.folders = [
            IndexedFolder(
                path=self.folders_list.item(i).text(),
                recursive=self.folders_list.item(i).checkState() == Qt.Checked,
            )
            for i in range(self.folders_list.count())
        ]
        config.excluded_extensions = [
            e.strip().lower().lstrip(".")
            for e in self.excluded_extensions_edit.text().split(",")
            if e.strip()
        ]
        config.excluded_patterns = [
            line.strip()
            for line in self.excluded_patterns_edit.toPlainText().splitlines()
            if line.strip()
        ]
        config.max_file_size_mb = self.max_size_spin.value()
        config.auto_update_enabled = self.auto_update_check.isChecked()
        config.auto_update_interval_minutes = self.interval_spin.value()
        config.ocr.enabled = self.ocr_enabled_check.isChecked()
        config.ocr.language = self.ocr_language_combo.currentText().strip() or "eng"
        config.ocr.max_pdf_pages = self.ocr_max_pages_spin.value()
        config.ocr.max_file_size_mb = self.ocr_max_size_spin.value()
        config.ocr.formats = [
            fmt for fmt, check in self.ocr_format_checks.items() if check.isChecked()
        ]

        if config.ocr.enabled and not is_tesseract_available():
            QMessageBox.warning(
                self, "Tesseract não encontrado", TESSERACT_INSTALL_INSTRUCTIONS
            )
        self.accept()

    def result_config(self) -> AppConfig:
        """Configuração editada (válida após ``exec()`` retornar Accepted)."""
        return self._config
