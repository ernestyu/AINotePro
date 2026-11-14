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

from PyQt6.QtCore import QObject, QPoint, QSize, Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QIntValidator, QFocusEvent, QPainter, QPalette
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMenu, QStyleFactory, QToolButton,
    QStyle, QStyleOptionComboBox, QVBoxLayout, QWidget,
)
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
    scope = dict(QObject=QObject, QWidget=QWidget, QComboBox=QComboBox, QEvent=QEvent,
                 QPoint=QPoint, QSize=QSize, Qt=Qt, QFrame=QFrame, QHBoxLayout=QHBoxLayout,
                 QListWidget=QListWidget, QListWidgetItem=QListWidgetItem,
                 QDialog=QDialog, QLabel=QLabel, QLineEdit=QLineEdit, QMenu=QMenu, QPainter=QPainter,
                 QPalette=QPalette,
                 QStyle=QStyle, QStyleOptionComboBox=QStyleOptionComboBox,
                 QStyleFactory=QStyleFactory, QToolButton=QToolButton, QVBoxLayout=QVBoxLayout,
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
        self.assertIn("self.image_checkbox.setEnabled(not advanced)", mode_source)
        self.assertNotIn("vision_supported", cap_source)
        self.assertNotIn("if not self.image_checkbox.isEnabled()", cap_source)
        check = QCheckBox("Image Recognition")
        try:
            check.setChecked(True)
            for provider in ("openai", "gemini", "ollama", "vllm", "deepseek"):
                check.setChecked(True)
                check.setEnabled(False)  # Advanced mode hides OCR.
                self.assertTrue(check.isChecked())
                check.setEnabled(True)  # Easy mode permits user-controlled vision.
                self.assertTrue(check.isChecked())
        finally:
            check.deleteLater()

    def test_real_checkbox_full_production_mode_and_provider_lifecycle(self):
        # Bind the actual TextTab methods to a lightweight QObject with real
        # Qt controls, avoiding Anki startup while executing the real branches.
        tree = ast.parse(SOURCE)
        tab = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == "TextTab")
        names = {"_update_field_mode_widgets", "_apply_provider_capabilities"}
        methods = [n for n in tab.body if isinstance(n, ast.FunctionDef)
                   and n.name in names]
        cls = ast.ClassDef(name="OCRModeOwner",
                           bases=[ast.Name(id="QObject", ctx=ast.Load())],
                           keywords=[], body=methods, decorator_list=[])
        scope = {
            "QObject": QObject,
            "Optional": __import__("typing").Optional,
            "NO_MODELS_ENDPOINT_PROVIDERS": set(),
            "models_endpoint_from_chat": lambda _value: "",
            "legacy_chat_endpoint": lambda value: value,
            "local_chat_endpoint": lambda value: value,
        }
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                     "<OCR methods>", "exec"), scope)
        owner = scope["OCRModeOwner"]()
        owner._field_mode = "easy"
        owner._active_provider = "openai"
        owner._service_map = lambda: owner._active_provider
        owner.cfg = type("Config", (), {
            "get_provider_config": lambda self, _domain, _provider: {"chat_endpoint": "https://example.test/v1/chat/completions"}
        })()
        owner.image_checkbox = QCheckBox("Image Recognition")
        owner.image_checkbox.setChecked(True)
        owner.batch_size_label = QWidget()
        owner.batch_size_combo = QComboBox()
        owner.reasoning_combo = QComboBox()
        owner.refresh_button = QWidget()
        owner.prompt_edit = QComboBox()
        owner._update_invalid_field_resolver = lambda: None
        for name in ("easy_source_label", "source_field_combo",
                     "easy_destination_label", "destination_field_combo",
                     "advanced_source_label", "advanced_source_fields",
                     "advanced_destination_label", "advanced_destination_fields"):
            setattr(owner, name, QWidget())
        try:
            owner._update_field_mode_widgets()
            owner._apply_provider_capabilities()
            self.assertTrue(owner.image_checkbox.isChecked())
            owner._field_mode = "advanced"
            owner._update_field_mode_widgets()
            owner._apply_provider_capabilities()  # Advanced batch finished.
            self.assertFalse(owner.image_checkbox.isEnabled())
            self.assertTrue(owner.image_checkbox.isChecked())
            owner._field_mode = "easy"
            owner._update_field_mode_widgets()
            owner._apply_provider_capabilities()
            self.assertTrue(owner.image_checkbox.isEnabled())
            self.assertTrue(owner.image_checkbox.isChecked())
            owner._active_provider = "vllm"
            owner._apply_provider_capabilities()
            self.assertTrue(owner.image_checkbox.isEnabled())
            self.assertTrue(owner.image_checkbox.isChecked())
            owner._field_mode = "advanced"
            owner._update_field_mode_widgets()
            owner._apply_provider_capabilities()
            self.assertFalse(owner.image_checkbox.isEnabled())
            self.assertTrue(owner.image_checkbox.isChecked())
        finally:
            owner.deleteLater()

    def test_real_field_combo_unavailable_item_can_be_unchecked(self):
        combo = self.CheckableFieldCombo()
        try:
            changes = []
            combo.selectionChanged.connect(lambda: changes.append(combo.selected_fields()))
            combo.set_fields(["Text", "Out", "Missing"], ["Text", "Missing"], {"Out"})
            self.assertEqual(combo.selected_fields(), ["Text", "Missing"])
            # An unavailable but previously selected field must remain removable.
            self.assertTrue(combo.item(2).flags() & Qt.ItemFlag.ItemIsEnabled)
            combo.item(2).setCheckState(Qt.CheckState.Unchecked)
            self.assertEqual(combo.selected_fields(), ["Text"])
            self.assertFalse(combo.item(1).flags() & Qt.ItemFlag.ItemIsEnabled)
            combo.set_disabled_fields(set())
            self.assertTrue(combo.item(1).flags() & Qt.ItemFlag.ItemIsEnabled)
            self.assertEqual(len(changes), 1)
        finally:
            combo.close()
            combo.deleteLater()

    def test_real_field_combo_renders_checkable_items_and_keeps_popup_open_for_mouse_multiselect(self):
        combo = self.CheckableFieldCombo()
        try:
            combo.set_fields(["Text", "Scenario", "Translation", "Takeaway"])
            for row in range(combo.count()):
                item = combo.item(row)
                self.assertTrue(item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
                self.assertTrue(item.flags() & Qt.ItemFlag.ItemIsEnabled)
                self.assertEqual(item.checkState(), Qt.CheckState.Unchecked)

            combo.show()
            combo.showPopup()
            self.app.processEvents()
            view = combo.listWidget()
            for row, expected in ((0, ["Text"]), (1, ["Text", "Scenario"])):
                rect = view.visualItemRect(combo.item(row))
                QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                                 pos=rect.topLeft() + QPoint(12, rect.height() // 2))
                self.app.processEvents()
                self.assertEqual(combo.selected_fields(), expected)
                self.assertEqual(combo.lineEdit().text(), ", ".join(expected))
                self.assertTrue(view.isVisible())
            combo.hidePopup()
            self.assertFalse(view.isVisible())
            combo.showPopup()
            self.app.processEvents()
            self.assertEqual(combo.selected_fields(), ["Text", "Scenario"])
            self.assertEqual(combo.item(0).checkState(), Qt.CheckState.Checked)
            self.assertEqual(combo.item(2).checkState(), Qt.CheckState.Unchecked)
        finally:
            combo.close()
            combo.deleteLater()

    def test_real_field_combo_uses_standard_combo_frame_and_full_click_target(self):
        combo = self.CheckableFieldCombo()
        provider = QComboBox()
        try:
            provider.addItem("OpenAI")
            combo.set_fields(["Text", "Scenario"])
            combo.resize(combo.sizeHint())
            self.assertEqual(combo.sizeHint().height(), provider.sizeHint().height())
            self.assertFalse(combo.lineEdit().hasFrame())
            self.assertFalse(combo.lineEdit().isVisible())
            self.assertEqual(combo._summary_label.text(), "Select fields…")
            combo.show()
            QTest.mouseClick(combo, Qt.MouseButton.LeftButton, pos=combo.rect().center())
            self.app.processEvents()
            self.assertTrue(combo.listWidget().isVisible())
            QTest.mouseClick(combo, Qt.MouseButton.LeftButton, pos=combo.rect().center())
            self.app.processEvents()
            self.assertFalse(combo.listWidget().isVisible())
        finally:
            combo.close()
            provider.close()
            combo.deleteLater()
            provider.deleteLater()

    def test_real_field_combo_popup_tracks_parent_and_hides_with_it(self):
        host = QWidget()
        layout = QVBoxLayout(host)
        combo = self.CheckableFieldCombo(host)
        layout.addWidget(combo)
        try:
            combo.set_fields(["Text", "Scenario", "Translation"])
            host.setGeometry(100, 100, 360, 180)
            host.show()
            self.app.processEvents()
            combo.showPopup()
            self.app.processEvents()
            self.assertTrue(combo._popup.windowType() & Qt.WindowType.Popup)
            self.assertEqual(combo._popup.pos(), combo.mapToGlobal(QPoint(0, combo.height())))

            host.move(160, 150)
            self.app.processEvents()
            self.assertEqual(combo._popup.pos(), combo.mapToGlobal(QPoint(0, combo.height())))

            host.resize(440, 180)
            self.app.processEvents()
            self.assertEqual(combo._popup.width(), combo.width() + 2)
            self.assertEqual(combo._popup.pos(), combo.mapToGlobal(QPoint(0, combo.height())))
            self.assertTrue(combo.listWidget().hasFocus())

            QTest.keyClick(combo.listWidget(), Qt.Key.Key_Escape)
            self.assertFalse(combo.listWidget().isVisible())
            self.assertTrue(host.isVisible())

            combo.showPopup()
            host.hide()
            self.app.processEvents()
            self.assertFalse(combo.listWidget().isVisible())
        finally:
            combo.hidePopup()
            host.close()
            combo.deleteLater()
            host.deleteLater()

    def test_real_field_combo_popup_stays_inside_available_screen(self):
        available = self.app.primaryScreen().availableGeometry()
        if available.height() < 300:
            self.skipTest("screen is too small to test upward popup placement")

        host = QWidget()
        combo = self.CheckableFieldCombo(host)
        host.setGeometry(available.left() + 10, available.bottom() - 160, 300, 150)
        combo.setGeometry(10, 115, 280, combo.sizeHint().height())
        try:
            combo.set_fields(["Text", "Scenario", "Translation"])
            host.show()
            self.app.processEvents()
            combo.showPopup()
            self.app.processEvents()

            popup = combo._popup.geometry()
            self.assertGreaterEqual(popup.left(), available.left())
            self.assertGreaterEqual(popup.top(), available.top())
            self.assertLessEqual(popup.right(), available.right())
            self.assertLessEqual(popup.bottom(), available.bottom())
            self.assertLess(popup.top(), combo.mapToGlobal(QPoint(0, 0)).y())
        finally:
            combo.hidePopup()
            host.close()
            combo.deleteLater()
            host.deleteLater()

    def test_real_field_combo_summary_keeps_full_selection_in_tooltip(self):
        combo = self.CheckableFieldCombo()
        names = ["Very long source field name", "Another long destination field name"]
        try:
            combo.set_fields(names, names)
            summary = ", ".join(names)
            self.assertEqual(combo.lineEdit().text(), summary)
            self.assertEqual(combo.lineEdit().toolTip(), summary)
            self.assertEqual(combo.toolTip(), summary)
        finally:
            combo.close()
            combo.deleteLater()

    def test_github_settings_uses_standard_button_style(self):
        init_source = SOURCE[SOURCE.index("# Get standard icons"):SOURCE.index("# Fields row")]
        self.assertIn('QPushButton("Settings")', init_source)
        self.assertNotIn("github_settings_button.setIcon", init_source)
        self.assertNotIn("setFixedSize", init_source)
        self.assertNotIn('setText("⚙")', init_source)
        self.assertNotIn("font-size: 22px", init_source)

    def test_real_field_combo_keyboard_multiselect_and_bidirectional_conflicts(self):
        source = self.CheckableFieldCombo()
        destination = self.CheckableFieldCombo()
        names = ["Text", "Scenario", "Translation", "Takeaway"]
        try:
            source.set_fields(names)
            destination.set_fields(names)
            source.selectionChanged.connect(
                lambda: destination.set_disabled_fields(set(source.selected_fields())))
            destination.selectionChanged.connect(
                lambda: source.set_disabled_fields(set(destination.selected_fields())))

            source.show()
            source.showPopup()
            self.app.processEvents()
            view = source.listWidget()
            view.setCurrentRow(0)
            QTest.keyClick(view, Qt.Key.Key_Space)
            QTest.keyClick(view, Qt.Key.Key_Down)
            QTest.keyClick(view, Qt.Key.Key_Space)
            self.app.processEvents()
            self.assertEqual(source.selected_fields(), ["Text", "Scenario"])
            self.assertFalse(destination.item(0).flags() & Qt.ItemFlag.ItemIsEnabled)
            self.assertFalse(destination.item(1).flags() & Qt.ItemFlag.ItemIsEnabled)
            self.assertTrue(destination.item(2).flags() & Qt.ItemFlag.ItemIsEnabled)
            self.assertTrue(destination.item(3).flags() & Qt.ItemFlag.ItemIsEnabled)

            source.item(1).setCheckState(Qt.CheckState.Unchecked)
            self.assertEqual(source.selected_fields(), ["Text"])
            self.assertTrue(destination.item(1).flags() & Qt.ItemFlag.ItemIsEnabled)
            self.assertFalse(destination.item(0).flags() & Qt.ItemFlag.ItemIsEnabled)
            QTest.keyClick(view, Qt.Key.Key_Escape)
            self.assertFalse(view.isVisible())
        finally:
            source.close()
            destination.close()
            source.deleteLater()
            destination.deleteLater()

    def test_note_type_refresh_keeps_missing_selection_removable(self):
        tree = ast.parse(SOURCE)
        tab = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == "TextTab")
        method = next(node for node in tab.body if isinstance(node, ast.FunctionDef)
                      and node.name == "_update_invalid_field_resolver")
        cls = ast.ClassDef(name="InvalidFieldOwner", bases=[ast.Name(id="QObject", ctx=ast.Load())],
                           keywords=[], body=[method], decorator_list=[])
        scope = {"QObject": QObject}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                     "<note type refresh>", "exec"), scope)
        owner = scope["InvalidFieldOwner"]()
        source = self.CheckableFieldCombo()
        destination = self.CheckableFieldCombo()
        try:
            source.set_fields(["Text", "Missing"], ["Missing"])
            destination.set_fields(["Text", "Missing"])
            owner._advanced_field_names = ["Text"]
            owner.advanced_source_fields = source
            owner.advanced_destination_fields = destination

            owner._update_invalid_field_resolver()
            self.assertTrue(source.item(1).flags() & Qt.ItemFlag.ItemIsEnabled)
            self.assertIn("unavailable in this Note Type", source.item(1).toolTip())

            source.item(1).setCheckState(Qt.CheckState.Unchecked)
            owner._update_invalid_field_resolver()
            self.assertFalse(source.item(1).flags() & Qt.ItemFlag.ItemIsEnabled)
            self.assertFalse(destination.item(1).flags() & Qt.ItemFlag.ItemIsEnabled)
        finally:
            source.close()
            destination.close()
            source.deleteLater()
            destination.deleteLater()
            owner.deleteLater()

    def test_provider_switch_preserves_existing_advanced_field_state(self):
        tree = ast.parse(SOURCE)
        tab = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == "TextTab")
        method = next(node for node in tab.body if isinstance(node, ast.FunctionDef)
                      and node.name == "_populate_provider_cfg")
        cls = ast.ClassDef(name="ProviderOwner", bases=[ast.Name(id="QObject", ctx=ast.Load())],
                           keywords=[], body=[method], decorator_list=[])
        scope = {"QObject": QObject, "showWarning": self.warnings.append}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                     "<provider switch>", "exec"), scope)
        owner = scope["ProviderOwner"]()
        source = self.CheckableFieldCombo()
        destination = self.CheckableFieldCombo()
        try:
            names = ["Text", "Scenario", "Translation", "Takeaway"]
            source.set_fields(names, ["Text", "Scenario"], {"Translation", "Takeaway"})
            destination.set_fields(names, ["Translation", "Takeaway"], {"Text", "Scenario"})
            expected = (source.selected_fields(), destination.selected_fields(),
                        [bool(source.item(i).flags() & Qt.ItemFlag.ItemIsEnabled) for i in range(source.count())],
                        [bool(destination.item(i).flags() & Qt.ItemFlag.ItemIsEnabled) for i in range(destination.count())])
            owner._provider_switching = False
            owner._service_map = lambda: "vllm"
            owner._active_provider = "openai"
            owner._save_current_provider_config = lambda **_kwargs: True
            owner.cfg = type("Config", (), {
                "get_provider_config": lambda _self, _domain, _provider: {
                    "chat_endpoint": "http://server:8000/v1/chat/completions",
                    "api_key": "", "model": "model", "temperature": 0.7,
                    "reasoning_by_model": {},
                },
                "set_active_provider": lambda _self, _domain, _provider: None,
            })()
            owner._legacy_base_url = ""
            owner._stored_chat_endpoint = ""
            owner._shown_chat_endpoint = ""
            owner.base_url_edit = QLineEdit()
            owner.endpoint_label = QLabel()
            owner.api_key_edit = QLineEdit()
            owner.model_combo = QComboBox(); owner.model_combo.setEditable(True)
            owner.temperature_edit = QLineEdit()
            owner.reasoning_combo = QComboBox(); owner.reasoning_combo.addItem("Default", "default")
            owner._reasoning_by_model = {}
            owner._active_model = ""
            owner._loading_provider = False
            owner._local_server_address = lambda value: value.rsplit("/v1/", 1)[0]
            owner._legacy_chat_endpoint = lambda value: value
            owner._apply_provider_capabilities = lambda _provider: None
            owner._restore_provider_selection = lambda _provider: None
            owner.advanced_source_fields = source
            owner.advanced_destination_fields = destination

            owner._populate_provider_cfg()
            actual = (source.selected_fields(), destination.selected_fields(),
                      [bool(source.item(i).flags() & Qt.ItemFlag.ItemIsEnabled) for i in range(source.count())],
                      [bool(destination.item(i).flags() & Qt.ItemFlag.ItemIsEnabled) for i in range(destination.count())])
            self.assertEqual(actual, expected)
        finally:
            source.close()
            destination.close()
            source.deleteLater()
            destination.deleteLater()
            owner.deleteLater()


if __name__ == "__main__":
    unittest.main()
