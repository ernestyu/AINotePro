"""GitHub repository settings; credentials remain in the native OS store."""
from __future__ import annotations

from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QLabel,
    QDialogButtonBox, QCheckBox, QPushButton, QMessageBox,
)
from aqt.utils import showWarning

from ..services.github_prompts import validate_settings


class GitHubPromptSettingsDialog(QDialog):
    def __init__(self, settings, has_saved_token=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GitHub AINotePro Library Settings")
        self.setMinimumWidth(660)
        root = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self._initial_repository = settings.get("repository", "").strip().casefold()
        self._initial_has_saved_token = bool(has_saved_token)

        self.repository = QLineEdit(settings.get("repository", ""))
        self.repository.setPlaceholderText("owner/repository")
        self.branch = QLineEdit(settings.get("branch", "main"))
        self.path = QLineEdit(settings.get("path", "ainotepro-library.json"))
        self.path.setMinimumWidth(430)
        self.path.setToolTip("Repository-relative path, e.g. anki/ainotepro-library.json")

        # Never place the stored secret (or masking bullets suggesting a value)
        # into the editor. An inactive, disabled editor denotes an existing
        # credential, and Replace is an explicit action.
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.replace_token = QPushButton("Replace Token")
        self.replace_token.clicked.connect(self._enable_token_replacement)
        token_row = QHBoxLayout()
        token_row.addWidget(self.token, 1)
        token_row.addWidget(self.replace_token)
        form.addRow("Repository:", self.repository)
        form.addRow("Branch:", self.branch)
        form.addRow("JSON path:", self.path)
        form.addRow("Access token:", token_row)
        root.addLayout(form)

        self.token_status = QLabel()
        root.addWidget(self.token_status)
        self.forget_token = QCheckBox("Remove saved token for this repository")
        root.addWidget(self.forget_token)
        self.repository.textChanged.connect(self._repository_edited)
        self.forget_token.toggled.connect(self._removal_changed)
        self._repository_edited(self.repository.text())

        hint = QLabel(
            "GitHub Token is stored per repository in the operating system "
            "credential store (macOS Keychain, Windows Credential Manager, "
            "or Linux Secret Service), not in user_config.json or the library. "
            "Saving or replacing a token requires confirmation. "
            "A relative JSON path may include directories."
        )
        hint.setWordWrap(True)
        root.addWidget(hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._accept_settings)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.value = None
        self.new_token = ""
        self.remove_saved_token = False

    def _saved_here(self):
        return (self._initial_has_saved_token and
                self.repository.text().strip().casefold() == self._initial_repository)

    def _repository_edited(self, _text):
        saved = self._saved_here()
        self.token.clear()
        self.token.setEnabled(not saved)
        self.token.setPlaceholderText(
            "Saved securely — click Replace Token to change"
            if saved else "Enter a new fine-grained GitHub token"
        )
        self.replace_token.setVisible(saved)
        self.replace_token.setEnabled(saved)
        self.forget_token.setEnabled(saved)
        self.forget_token.setChecked(False)
        self.token_status.setText(
            "Token status: Saved in system credential store"
            if saved else "Token status: Not saved for this repository"
        )

    def _enable_token_replacement(self):
        if not self._saved_here():
            return
        self.forget_token.setChecked(False)
        self.token.setEnabled(True)
        self.token.clear()
        self.token.setPlaceholderText("Enter replacement token")
        self.replace_token.setEnabled(False)
        self.token.setFocus()

    def _removal_changed(self, checked):
        if checked:
            self.token.clear()
            self.token.setEnabled(False)
            self.replace_token.setEnabled(False)
            self.token_status.setText("Token status: Will be removed on OK")
        else:
            self._repository_edited(self.repository.text())

    def _accept_settings(self):
        try:
            self.value = validate_settings({
                "repository": self.repository.text(),
                "branch": self.branch.text(),
                "path": self.path.text(),
            })
        except ValueError as exc:
            showWarning(str(exc))
            return
        self.new_token = self.token.text().strip() if self.token.isEnabled() else ""
        self.remove_saved_token = self.forget_token.isChecked()
        if self.new_token and self.remove_saved_token:
            showWarning("Choose either replacing or removing the token.")
            return
        if self.new_token or self.remove_saved_token:
            action = ("remove the saved GitHub token from"
                      if self.remove_saved_token else
                      "save the GitHub token securely for")
            confirmation = QMessageBox.question(
                self, "Confirm GitHub Token Storage",
                f"Do you want to {action} {self.value['repository']}?\n\n"
                "The token is stored in the operating system credential store, "
                "not in AINotePro's configuration or GitHub library.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirmation != QMessageBox.StandardButton.Yes:
                return
        self.accept()
