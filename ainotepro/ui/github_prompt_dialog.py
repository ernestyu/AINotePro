"""GitHub repository settings; credentials are saved in the native OS store."""
from __future__ import annotations

from aqt.qt import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QLabel,
    QDialogButtonBox, QCheckBox,
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
        self.repository = QLineEdit(settings.get("repository", ""))
        self.repository.setPlaceholderText("owner/repository")
        self.branch = QLineEdit(settings.get("branch", "main"))
        self.path = QLineEdit(settings.get("path", "ainotepro-library.json"))
        self.path.setMinimumWidth(430)
        self.path.setToolTip("Repository-relative path, e.g. anki/ainotepro-library.json")
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        if has_saved_token:
            self.token.setPlaceholderText("Saved in system credential store — leave blank to keep")
        else:
            self.token.setPlaceholderText("Paste a fine-grained GitHub token to save securely")
        form.addRow("Repository:", self.repository)
        form.addRow("Branch:", self.branch)
        form.addRow("JSON path:", self.path)
        form.addRow("Access token:", self.token)
        root.addLayout(form)
        self.forget_token = QCheckBox("Remove saved token for this repository")
        self.forget_token.setEnabled(has_saved_token)
        root.addWidget(self.forget_token)
        hint = QLabel(
            "A relative JSON path can include directories (for example, "
            "anki/ainotepro-library.json). Use a fine-grained token with "
            "Contents read/write access to this repository. "
            "The token is stored in the operating system credential store "
            "(macOS Keychain, Windows Credential Manager, or Linux Secret Service), "
            "not in user_config.json or the exported library."
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
        self.new_token = self.token.text().strip()
        self.remove_saved_token = self.forget_token.isChecked()
        if self.new_token and self.remove_saved_token:
            showWarning("Choose either a new token or Remove saved token, not both.")
            return
        self.accept()
