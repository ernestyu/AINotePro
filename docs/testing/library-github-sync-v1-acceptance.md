# Library & GitHub Sync V1 — Acceptance Checklist

Scope: AINotePro.library v1 (Easy + Advanced prompts + Audio Profiles), GitHub
Contents API, native OS credentials. This is a **manual release gate**, not
evidence that all platforms have already been tested.

## Automated verification

GitHub Actions: .github/workflows/library-sync-tests.yml

- Ubuntu Python 3.11 and 3.13.
- macOS Python 3.13.
- Windows Python 3.13.
- Unit tests exercise actual library, ConfigManager, HTTP request and
  compensation code with temporary files and mocked credentials/API.
- UI-state unit tests execute extracted production methods against fake Qt
  controls; they **do not** prove true Anki/Qt lifecycle or OS Keychain behavior.
- Tests must not call real user repositories or persist real secrets.

## Expected V1 sync behavior

1. Each import or GitHub load is non-destructive. Conflicting same-name entries
   acquire (1), (2), etc. and keep the old entry unchanged.
2. Local name-to-content mappings can differ across machines after a conflict.
   The required invariant is preserved content union and no new numbered copies
   after repeated Save/Load. A deterministic cross-machine name map is **not**
   required in V1.
3. Different names with identical text may be intentional aliases and are kept.
4. Prompt/Audio name identity uses Unicode NFC and casefold; duplicate keys are
   invalid, including "A"/"a" and composed/decomposed spelling.
5. Profile JSON outputs only V1 schema fields. Unknown nested keys must not be
   present in exported JSON or the GitHub PUT content.
6. Audio Profile IDs and current local selection are not exported. Existing
   local IDs and selection stay unchanged on import.
7. A failed full-library validation never writes any of the three domains. The
   established, migrated local configuration is committed in one atomic write.
8. GitHub Credentials and Text Provider keys are never exported or logged.
9. Repository/token changes can touch two stores (OS vault and user_config).
   If either store fails, compensation is attempted and the user is informed
   whether restoration succeeded or a partial change remains possible.

## Actual Anki/Qt acceptance, **per supported desktop OS**

Use a disposable repository and a fine-grained token scoped only to that repo.
Never paste the token into logs, issues, tickets, or screenshots.

- [ ] Open Settings with no token: status "Not saved", token input enabled.
- [ ] Save token after Yes confirmation. Verify success and reopen dialog:
      status "Saved", input disabled, actual secret not displayed.
- [ ] Cancel token save: nothing written. Restart Anki: saved token persists.
- [ ] For two separate repositories with saved tokens A and B: edit repository
      A -> B -> A. Both show the correct saved state without re-entering tokens.
- [ ] Set Repository C (no token): status "Not saved"; locked/unavailable
      keyring shows explicit error, not "Not saved".
- [ ] Replace and Remove ask for confirmation and only affect the selected
      repository. Cancel leaves the original token unchanged.
- [ ] Simulate/inspect a credentials/settings save failure: no unhandled Anki
      exception and message describes rollback or partial state.
- [ ] Save to a nested path; then Load on a fresh Anki configuration.
      Both Easy/Advanced prompts and Audio Profiles appear.
- [ ] Load twice: counts unchanged, no new (2)/(3) copies. Conflict renamed
      without altering an existing saved prompt or UUID.
- [ ] Switch Text Easy/Advanced and Audio tabs after Load; saved entries appear
      without stale controls or dangling callbacks.
- [ ] Start GitHub Load, close the main dialog before it completes, and verify
      no access to a destroyed Qt widget, no blocked shutdown or crash.
- [ ] Simulate inaccessible repository, invalid branch, HTTP rate limit and
      disabled network; the plugin reports the failing operation and no secret
      appears in its rotating diagnostic log or Anki error window.

Platform-specific notes:

- macOS: verify native Keychain permission prompts and repeated read/write.
- Windows: verify Credential Manager persistence, 512-byte input limit, replacement.
- Linux: verify Secret Service with an unlocked keyring; without secret-tool
  only public anonymous loading is expected to work if already configured.
- The CI matrix runs on all three operating systems but uses **mocked OS vaults**.
  Do not mark the real-platform acceptance items complete based on green CI.
