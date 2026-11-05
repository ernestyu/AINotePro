"""Repository settings for GitHub prompt sync; token is session-only."""
from __future__ import annotations

from aqt.qt import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QLabel,
                    QDialogButtonBox)
from aqt.utils import showWarning

from ..services.github_prompts import validate_settings


class GitHubPromptSettingsDialog(QDialog):
    def __init__(self, settings, session_token="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("GitHub AINotePro Library Settings")
        self.setMinimumWidth(470)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.repository = QLineEdit(settings.get("repository", ""))
        self.repository.setPlaceholderText("owner/repository")
        self.branch = QLineEdit(settings.get("branch", "main"))
        self.path = QLineEdit(settings.get("path", "ainotepro-library.json"))
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.setPlaceholderText("Token kept for this Anki session" if session_token else
                                      "Fine-grained token (not saved to disk)")
        form.addRow("Repository:", self.repository)
        form.addRow("Branch:", self.branch)
        form.addRow("JSON path:", self.path)
        form.addRow("Access token:", self.token)
        root.addLayout(form)
        hint = QLabel("Use a fine-grained GitHub token with Contents read/write access "
                      "to only the selected repository. The token is never saved to "
                      "user_config.json; enter it again after restarting Anki.")
        hint.setWordWrap(True)
        root.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_settings)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.value = None
        self.session_token = session_token

    def _accept_settings(self):
        try:
            self.value = validate_settings({"repository": self.repository.text(),
                                             "branch": self.branch.text(),
                                             "path": self.path.text()})
        except ValueError as exc:
            showWarning(str(exc))
            return
        self.session_token = self.token.text().strip() or self.session_token
        self.accept()
