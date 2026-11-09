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
- **v1.2.0 (pending real Anki acceptance):** Test editable Batch Size (dropdown 1–10, default 1, manual range 1–99, two digits), persistence and removed Resolve button with invalid fields still removable, Easy OCR visibility, B=1 original JSON, B=10 JSONL 10→2→next 10, duplicate/unknown IDs, truncated or malformed lines, three zero-progress stops, explicit context-limit popup, and non-cancel partial commit.
- Verify one Anki Undo group and snapshot-conflict skips across multiple requests; cancel before commit must not write, cancel after scheduling must report actual per-note outcomes. Close the TextTab during queued/active commit and confirm the background coordinator still settles without accessing deleted widgets; perform real UI/Undo tests on Windows and Linux (plus the platforms required by the Advanced SPEC).
- Check `.github/workflows/advanced-batch-tests.yml` on the exact V1.2.0 candidate commit. Four-platform headless tests do not count as real Anki acceptance.
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
- **Source version is now 1.2.0:** `manifest.json` is the single authoritative version; `ainotepro/version.py` reads it for the dialog title (`AINotePro — v1.2.0`), while `__init__.py` intentionally does not duplicate a numeric version. Verify the version in the packaged add-on. This source merge is **not** an AnkiWeb release; finish the user's real Anki/Qt and Undo checks, back up `user_files`, and explicitly authorize packaging/publication. Older single-prompt export JSON is not accepted by the unified Library Import.
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

## 4. Release source and distributable branches

The authoritative source release is **main**, tagged \`v1.2.0\`. Keep all source code,
tests, documentation, and CI workflows on main.

The **addon/v1.2.0** branch is a distribution-only snapshot of the plugin code.
Its root contains \`__init__.py\`, \`manifest.json\`, \`ainotepro/\`, \`libs/\`,
\`user_files/README.txt\`, and the required license/privacy notices. It excludes
\`docs/\`, \`tests/\`, \`scripts/\`, \`.github/\`, generated logs, caches and backups.

Build the package *from the addon branch* without having to check it out:

~~~bash
git fetch origin --prune --tags
git archive --format=zip --output=AINotePro-v1.2.0.ankiaddon origin/addon/v1.2.0
unzip -t AINotePro-v1.2.0.ankiaddon
unzip -p AINotePro-v1.2.0.ankiaddon manifest.json
shasum -a 256 AINotePro-v1.2.0.ankiaddon
~~~

The archive's top level must contain the add-on entrypoint directly, not a
wrapping directory. Do not export \`main\` as the installable archive, since
that would include development files. GitHub releases and tags refer to the
source commit on \`main\`; the \`.ankiaddon\` release asset is built from
\`addon/v1.2.0\`. Before replacing an existing published tag or release asset,
confirm that you are updating the intended version and record its checksum.
The source release does not by itself publish to AnkiWeb.

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
