"""Small compensating transaction for GitHub settings and native credentials.

The OS credential store and user_config.json cannot participate in one atomic
transaction. Snapshot both, verify each write, and compensate on failures.
Never log or include secrets in exceptions.
"""
from __future__ import annotations


class GitHubSettingsTransactionError(RuntimeError):
    def __init__(self, message, *, partial=False):
        self.partial = partial
        super().__init__(message)


def apply_github_settings(
    proposed, *, new_token="", remove_token=False,
    read_settings, save_settings, restore_settings,
    get_token, set_token, delete_token,
):
    if new_token and remove_token:
        raise ValueError("Cannot replace and remove a token simultaneously")
    old_settings = read_settings()
    target = proposed["repository"]
    credential_change = bool(new_token or remove_token)
    old_token = get_token(target) if credential_change else None

    try:
        if new_token:
            set_token(target, new_token)
            if get_token(target) != new_token:
                raise RuntimeError("Credential verification failed after save")
        elif remove_token:
            delete_token(target)
            if get_token(target):
                raise RuntimeError("Credential still present after deletion")
        save_settings(proposed)
        if read_settings() != proposed:
            raise RuntimeError("GitHub settings did not persist")
    except Exception as exc:
        failures = []
        # Credential writes can fail after a partial change. Restore even if
        # the first write raised, so the old credential remains authoritative.
        if credential_change:
            try:
                if old_token:
                    set_token(target, old_token)
                else:
                    delete_token(target)
                if get_token(target) != old_token:
                    raise RuntimeError("Credential rollback verification failed")
            except Exception as rollback_exc:
                failures.append(f"credential rollback: {type(rollback_exc).__name__}")
        try:
            if read_settings() != old_settings:
                restore_settings(old_settings)
                if read_settings() != old_settings:
                    raise RuntimeError("Settings rollback verification failed")
        except Exception as rollback_exc:
            failures.append(f"settings rollback: {type(rollback_exc).__name__}")
        # Never stringify the credential values or raw provider responses.
        stage = type(exc).__name__
        if failures:
            raise GitHubSettingsTransactionError(
                f"GitHub settings update failed ({stage}); PARTIAL CHANGE POSSIBLE. "
                f"Recovery failed: {', '.join(failures)}. Reopen GitHub Settings, "
                "check the repository and saved-token status before retrying.",
                partial=True,
            ) from None
        raise GitHubSettingsTransactionError(
            f"GitHub settings update failed ({stage}); previous settings "
            "and credential were restored.",
        ) from None
    return "saved" if new_token else "removed" if remove_token else "unchanged"
