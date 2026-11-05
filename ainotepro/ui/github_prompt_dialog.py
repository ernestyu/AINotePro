"""GitHub settings: explicit native-credential state and consent on mutation."""
from __future__ import annotations

from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QLabel,
    QDialogButtonBox, QCheckBox, QPushButton, QMessageBox, QTimer,
)
from aqt.utils import showWarning

from ..services.github_prompts import validate_settings
from ..services.github_credentials import get_token


class GitHubPromptSettingsDialog(QDialog):
    def __init__(self, settings, has_saved_token=False, parent=None,
                 credential_lookup=None):
        super().__init__(parent)
        self.setWindowTitle("GitHub AINotePro Library Settings")
        self.setMinimumWidth(660)
        self._credential_lookup = credential_lookup or get_token
        self._credential_status = "checking"
        self._checked_repository = None

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
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.setInterval(300)
        self._status_timer.timeout.connect(self._refresh_token_status)
        self.repository.textChanged.connect(self._repository_edited)
        self.forget_token.toggled.connect(self._removal_changed)

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

        # A previously checked initial repository may use the caller's state.
        repo = self.repository.text().strip().casefold()
        if repo:
            self._show_status(repo, "saved" if has_saved_token else "missing")
        else:
            self._show_status(None, "invalid")

    def _show_status(self, repository, status):
        self._credential_status = status
        self._checked_repository = repository
        self.token.clear()
        saved = status == "saved"
        self.token.setEnabled(status == "missing")
        self.token.setPlaceholderText(
            "Saved securely — click Replace Token to change"
            if saved else "Enter a fine-grained GitHub token"
            if status == "missing" else ""
        )
        self.replace_token.setVisible(saved)
        self.replace_token.setEnabled(saved)
        self.forget_token.blockSignals(True)
        try:
            self.forget_token.setChecked(False)
        finally:
            self.forget_token.blockSignals(False)
        self.forget_token.setEnabled(saved)
        labels = {
            "saved": "Token status: Saved in system credential store",
            "missing": "Token status: Not saved for this repository",
            "checking": "Token status: Checking system credential store...",
            "invalid": "Token status: Enter a valid owner/repository",
            "error": "Token status: Cannot access the system credential store",
        }
        self.token_status.setText(labels[status])

    def _repository_edited(self, _text):
        self._status_timer.stop()
        self._show_status(None, "checking")
        self._status_timer.start()

    def _refresh_token_status(self):
        repository = self.repository.text().strip()
        try:
            # Validate only the repository while the user may still be typing
            # the independent branch/path controls.
            validate_settings({
                "repository": repository,
                "branch": "main",
                "path": "ainotepro-library.json",
            })
        except ValueError:
            self._show_status(None, "invalid")
            return
        try:
            saved = bool(self._credential_lookup(repository))
        except Exception:
            # A locked/broken keyring is not equivalent to 'no token'.
            self._show_status(repository.casefold(), "error")
            return
        self._show_status(repository.casefold(), "saved" if saved else "missing")

    def _enable_token_replacement(self):
        if self._credential_status != "saved":
            return
        self.forget_token.setChecked(False)
        self.token.setEnabled(True)
        self.token.clear()
        self.token.setPlaceholderText("Enter replacement token")
        self.replace_token.setEnabled(False)
        self.token_status.setText("Token status: Enter replacement; old token retained until OK")
        self.token.setFocus()

    def _removal_changed(self, checked):
        if checked:
            self.token.clear()
            self.token.setEnabled(False)
            self.replace_token.setEnabled(False)
            self.token_status.setText("Token status: Will be removed on OK")
        elif self._credential_status == "saved":
            self.token.setEnabled(False)
            self.replace_token.setEnabled(True)
            self.token_status.setText("Token status: Saved in system credential store")

    def _accept_settings(self):
        try:
            value = validate_settings({
                "repository": self.repository.text(),
                "branch": self.branch.text(),
                "path": self.path.text(),
            })
        except ValueError as exc:
            showWarning(str(exc))
            return
        repo = value["repository"].casefold()
        if self._checked_repository != repo or self._credential_status == "checking":
            self._status_timer.stop()
            self._refresh_token_status()
        if self._credential_status in ("invalid", "checking", "error"):
            showWarning("Could not verify Token status for this repository. "
                        "Check the operating system credential store and retry.")
            return
        new_token = self.token.text().strip() if self.token.isEnabled() else ""
        remove_saved_token = self.forget_token.isChecked()
        if new_token and remove_saved_token:
            showWarning("Choose either replacing or removing the token.")
            return
        if new_token or remove_saved_token:
            action = ("remove the saved GitHub token from"
                      if remove_saved_token else "save the GitHub token securely for")
            confirmation = QMessageBox.question(
                self, "Confirm GitHub Token Storage",
                f"Do you want to {action} {value['repository']}?\n\n"
                "The token is stored in the operating system credential store, "
                "not in AINotePro's configuration or GitHub library.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirmation != QMessageBox.StandardButton.Yes:
                return
        self.value = value
        self.new_token = new_token
        self.remove_saved_token = remove_saved_token
        self.accept()
