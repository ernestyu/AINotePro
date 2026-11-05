# AINotePro Release Checklist

[English](RELEASE_CHECKLIST.md) | [简体中文](RELEASE_CHECKLIST.zh-CN.md)

Use this checklist before publishing a new AINotePro build to AnkiWeb.

## 1. Pre-release checks

- Start Anki with the add-on enabled and confirm no startup traceback appears.
- Open the Browse window and confirm the `AINotePro` menu appears.
- Open the dialog from the Browse menu with one selected note.
- Open the dialog from the editor toolbar button.
- Generate text into a destination field for one note.
- Generate text into destination fields for two or more selected notes.
- Test Advanced source/destination declarations and strict JSON output, including more than 100 selected valid notes without an arbitrary batch-size rejection. Confirm invalid notes still reject the entire batch before requests.
- Save, load, delete, import, and export a prompt.
- Confirm the obsolete `Online` prompt button is absent, and New/Save/Save As/Delete plus Import/Export remain functional.
- Use `Check` for at least one remote provider.
- Confirm Reasoning is selectable for all 13 provider presets; Model Default omits reasoning control fields. For a custom OpenAI-compatible NInfer endpoint, verify Off sends `reasoning_effort: "none"` and check its actual server behavior. Unsupported official endpoints must not be reported as proven to honor a strength setting.
- Verify the Text label reads `Temperature`, and DEBUG logs reflect the final outgoing Temperature, Reasoning, token-limit and stream fields without API keys, prompts or full responses.
- Verify the footer's left group (GitHub link → Restore Default LLM Parameters → Help) and right group (Close → Generate). Confirm Restore affects only the selected provider, preserves its API key and local server address, and is hidden on Audio.
- Confirm the last successful model is still selected after closing and reopening the dialog.
- On macOS, visually confirm that each Audio Speed/Volume slider has a visible Qt-drawn left/right arrow button; check both directions adjust 1% and disabled states remain correct.
- Generate audio and confirm `[sound:...]` is appended to the configured field. Verify Edge/Kokoro selection and Audio Profile switching without unrequested saves. Edge voice labels show region codes before names (for example, `US-AriaNeural` and `GB-SoniaNeural`); voice IDs and filtering remain unchanged.
- **v1.1.1 Library:** Export one unified JSON and verify it contains saved Easy/Advanced prompts and four-slot Edge/Kokoro Audio Profiles, but excludes provider API keys and Audio UUIDs. Import into a disposable Anki profile; verify conflicts are renamed, repeat imports are idempotent, and original Profile UUIDs and selection remain unchanged.
- **v1.1.1 GitHub:** Use a disposable repository and least-privilege fine-grained token. Verify Save/Load with nested JSON path, public/private access behavior, repository-switch token status, Replace/Remove confirmations, and non-destructive merges. Confirm a public repository exposes library contents; never test with real private prompts.
- **v1.1.1 Audio and batch preflight:** Verify four Voice blocks, migration of saved three-slot Profiles, and Edge/Kokoro generation. Mixed Note Types must be rejected before Text Easy or Audio requests and note writes, while multiple card templates of one Note Type remain supported.
- Verify the V1.1.1 GitHub-synchronization acceptance items in `docs/testing/library-github-sync-v1-acceptance.md` on each supported OS. GitHub Actions tests mock native credentials and do not replace real Keychain/Credential Manager/Secret Service testing.
- Check the four-platform matrix in `.github/workflows/library-sync-tests.yml` for the exact commit being released. If any required CI job is queued or fails, do not record CI as passed.
- Confirm `manifest.json` and `__init__.py` both report version 1.1.1, and back up `user_files` before upgrade. Older single-prompt export JSON is not accepted by the new unified Library Import.
- Test image OCR with a known vision-capable endpoint if advertising image-source support in the release notes.
- Confirm `user_files/user_config.json` and prompt files survive an add-on upgrade.
- Confirm failed text generation does not write `[Error]` into destination fields.
- Confirm image OCR refuses `file://` paths outside Anki's media folder.
- Confirm image OCR refuses remote `http://` and `https://` image URLs.

## 2. Documentation checks

- Update `README.md` and `README.zh-CN.md` together.
- Update `docs/ANKIWEB_DESCRIPTION.md` and `docs/ANKIWEB_DESCRIPTION.zh-CN.md` together.
- Update `changelog.md` and `changelog.zh-CN.md` together.
- Update both language versions of this checklist and the privacy policy when behaviors change.
- Confirm the support URL works.
- Confirm privacy wording still matches the actual network behavior.
- Confirm `LICENSE` and `THIRD_PARTY_NOTICES.md` are still accurate.
- Confirm every vendored dependency in `libs/` includes its license text or distribution metadata.

## 3. Clean files before packaging

Remove generated and local-only files from the package:

- `__pycache__/`
- `*.pyc`
- `*.pyo`
- `user_data/`
- `user_files/user_config.json`
- `user_files/gen_text/`
- `ainotepro/logs/`
- `.git/`
- `.DS_Store`
- `meta.json`
- `*.bak`

`meta.json` is generated by Anki for installed add-ons and should not be treated as the source of release metadata.

## 4. Build the `.ankiaddon`

From the add-on root:

```bash
find . -name "__pycache__" -type d -prune -exec rm -rf {} +
rm -f ../AINotePro.ankiaddon
zip -r ../AINotePro.ankiaddon * \
  -x "user_data/*" "user_files/*" "ainotepro/logs/*" "*.pyc" "*.pyo" ".git/*" "*.DS_Store" "*.bak" "meta.json"
zip -ur ../AINotePro.ankiaddon user_files/README.txt
```

Verify the archive layout:

```bash
zipinfo -1 ../AINotePro.ankiaddon | head
```

The first-level contents should look like:

```text
__init__.py
ainotepro/...
libs/...
manifest.json
README.md
user_files/README.txt
```

Do not upload an archive whose contents are wrapped inside `AINotePro/`.

## 5. Upload to AnkiWeb

1. Go to `https://ankiweb.net/shared/addons/`.
2. Use the upload flow for add-ons.
3. Upload the `.ankiaddon` file.
4. Use the title `AINotePro - AI-powered note enhancement for Anki`.
5. Use the GitHub issues page as the support URL.
6. Paste the text from `docs/ANKIWEB_DESCRIPTION.md`.
7. Set the tested Anki version information according to the upload form.

## 6. After upload

- Install the add-on from AnkiWeb in a clean Anki profile.
- Confirm startup, Browse menu, editor toolbar button, text generation, prompt save/delete, and audio generation.
- Add the AnkiWeb code to `README.md`.
- Tag the release in the source repository.
