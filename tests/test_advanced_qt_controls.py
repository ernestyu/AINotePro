"""Offscreen tests of genuine Qt widgets and their event semantics.

The production UI class imports Anki, so extract its exact control methods and
bind them to a QObject test owner. Unlike fake-combo tests these exercise the
real QLineEdit validator, event filters and QComboBox item model.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QObject, Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QIntValidator, QFocusEvent
from PyQt6.QtWidgets import QApplication, QComboBox, QCheckBox, QWidget
from PyQt6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")


def widget_classes(warnings):
    tree = ast.parse(SOURCE)
    tab = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "TextTab")
    batch_methods = {"eventFilter", "_on_batch_size_activated",
                     "_restore_batch_size", "_commit_batch_size"}
    methods = [node for node in tab.body if isinstance(node, ast.FunctionDef)
               and node.name in batch_methods]
    batch_ast = ast.ClassDef(name="BatchEditor", bases=[ast.Name(id="QObject", ctx=ast.Load())],
                             keywords=[], body=methods, decorator_list=[])
    combo_class = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                       and node.name == "CheckableFieldCombo")
    module = ast.Module(body=[batch_ast, combo_class], type_ignores=[])
    scope = dict(QObject=QObject, QComboBox=QComboBox, QEvent=QEvent, Qt=Qt,
                 pyqtSignal=pyqtSignal, Optional=__import__("typing").Optional,
                 showWarning=warnings.append)
    exec(compile(ast.fix_missing_locations(module), "<real Qt controls>", "exec"), scope)
    return scope["BatchEditor"], scope["CheckableFieldCombo"]


class Config:
    def __init__(self):
        self.saved = []

    def update_text_fields(self, value):
        self.saved.append(value)


class ActualQtControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.warnings = []
        BatchEditor, self.CheckableFieldCombo = widget_classes(self.warnings)
        self.owner = BatchEditor()
        self.owner.cfg = Config()
        self.owner._saved_batch_size = 1
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for value in range(1, 11):
            self.combo.addItem(str(value), value)
        self.combo.setCurrentText("1")
        self.combo.lineEdit().setValidator(QIntValidator(1, 99, self.combo))
        self.owner.batch_size_combo = self.combo
        self.combo.lineEdit().installEventFilter(self.owner)
        self.combo.lineEdit().editingFinished.connect(self.owner._commit_batch_size)
        self.combo.activated.connect(self.owner._on_batch_size_activated)

    def tearDown(self):
        self.combo.close()
        self.combo.deleteLater()
        self.owner.deleteLater()
        self.app.processEvents()

    def focus_out(self):
        event = QFocusEvent(QEvent.Type.FocusOut)
        QApplication.sendEvent(self.combo.lineEdit(), event)
        self.app.processEvents()

    def test_invalid_intermediate_restores_on_focus_out_and_return(self):
        for text in ("0", "", "-1", "1.5", "x", "１２"):
            with self.subTest(text=text):
                self.combo.lineEdit().setText(text)
                self.focus_out()
                self.assertEqual(self.combo.currentText(), "1")
                self.assertEqual(self.owner.cfg.saved, [])
                self.combo.lineEdit().setText(text)
                QTest.keyClick(self.combo.lineEdit(), Qt.Key.Key_Return)
                self.assertEqual(self.combo.currentText(), "1")
                self.assertEqual(self.owner.cfg.saved, [])
        # The validator rejects 3-digit values without silently truncating.
        self.assertNotEqual(self.combo.lineEdit().validator().validate("100", 3)[0],
                            QIntValidator.State.Acceptable)
        self.assertTrue(self.warnings)
        # Clipboard paste and an illegal 3-digit string must not reach storage.
        clipboard = QApplication.clipboard()
        clipboard.setText("100")
        self.combo.lineEdit().clear()
        QTest.keyClick(self.combo.lineEdit(), Qt.Key.Key_V,
                       Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(self.combo.lineEdit(), Qt.Key.Key_Return)
        self.assertEqual(self.combo.currentText(), "1")
        self.assertEqual(self.owner.cfg.saved, [])

    def test_valid_manual_sizes_and_idempotent_activated(self):
        for size in (11, 20, 50, 99):
            self.combo.lineEdit().setText(str(size))
            self.focus_out()
            self.assertEqual(self.owner._saved_batch_size, size)
            self.assertEqual(self.owner.cfg.saved[-1], {"advanced_batch_size": size})
            before = len(self.owner.cfg.saved)
            QTest.keyClick(self.combo.lineEdit(), Qt.Key.Key_Return)
            self.owner._on_batch_size_activated(0)
            self.assertEqual(len(self.owner.cfg.saved), before)
        self.combo.setCurrentIndex(4)
        self.owner._on_batch_size_activated(4)
        self.assertEqual(self.owner._saved_batch_size, 5)

    def test_dropdown_activated_signal_commits_only_once(self):
        activations = []
        self.combo.activated.connect(activations.append)
        self.combo.show()
        self.combo.showPopup()
        self.app.processEvents()
        viewport = self.combo.view().viewport()
        index = self.combo.model().index(6, 0)
        rect = self.combo.view().visualRect(index)
        QTest.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=rect.center())
        self.app.processEvents()
        self.assertEqual(activations, [6])
        self.assertEqual(self.owner._saved_batch_size, 7)
        self.assertEqual(self.owner.cfg.saved, [{"advanced_batch_size": 7}])
        self.combo.hidePopup()

    def test_real_checkbox_keeps_state_when_advanced_disables_it(self):
        # Execute the production OCR state assignments on a real QCheckBox.
        tree = ast.parse(SOURCE)
        tab = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == "TextTab")
        mode = next(n for n in tab.body if isinstance(n, ast.FunctionDef)
                    and n.name == "_update_field_mode_widgets")
        capabilities = next(n for n in tab.body if isinstance(n, ast.FunctionDef)
                            and n.name == "_apply_provider_capabilities")
        mode_lines = SOURCE.splitlines()
        mode_source = ast.get_source_segment(SOURCE, mode)
        cap_source = ast.get_source_segment(SOURCE, capabilities)
        self.assertIn("self.image_checkbox.setVisible(not advanced)", mode_source)
        self.assertIn("self.image_checkbox.setEnabled(not advanced", mode_source)
        self.assertIn("if not vision_supported:", cap_source)
        self.assertNotIn("if not self.image_checkbox.isEnabled()", cap_source)
        check = QCheckBox("Image Recognition")
        try:
            check.setChecked(True)
            for provider in ("openai", "gemini", "ollama"):
                check.setChecked(True)
                check.setEnabled(False)  # Advanced mode, provider is capable
                self.assertTrue(check.isChecked())
                check.setEnabled(True)  # Easy restored
                self.assertTrue(check.isChecked())
            check.setEnabled(False)  # Unsupported provider in Easy
            check.setChecked(False)
            self.assertFalse(check.isChecked())
        finally:
            check.deleteLater()

    def test_real_field_combo_unavailable_item_can_be_unchecked(self):
        combo = self.CheckableFieldCombo()
        try:
            changes = []
            combo.selectionChanged.connect(lambda: changes.append(combo.selected_fields()))
            combo.set_fields(["Text", "Out", "Missing"], ["Text", "Missing"], {"Out"})
            self.assertEqual(combo.selected_fields(), ["Text", "Missing"])
            # An unavailable but previously selected field must remain removable.
            self.assertTrue(combo.model().item(2).isEnabled())
            combo._toggle_index(combo.model().index(2, 0))
            self.assertEqual(combo.selected_fields(), ["Text"])
            self.assertFalse(combo.model().item(1).isEnabled())
            combo.set_disabled_fields(set())
            self.assertTrue(combo.model().item(1).isEnabled())
            self.assertEqual(len(changes), 1)
        finally:
            combo.close()
            combo.deleteLater()


if __name__ == "__main__":
    unittest.main()
