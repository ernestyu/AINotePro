# AINotePro

[English](README.md) | [简体中文](README.zh-CN.md)

AINotePro is an Anki add-on for adding AI-generated text and audio to note fields. It can be opened from the Browse window menu or from the editor toolbar button above a note.

## Features

- Generate text in **Easy** mode (single source/destination) or **Advanced** mode (multiple source/destination fields, with batch size 1–99 and independently validated JSONL output for multiple notes).
- Use saved prompt templates with `{Source Field}` or `{Source}` placeholders.
- Save, load, and delete prompt templates; import/export a complete library containing both Text prompt modes and saved Audio Profiles in one JSON file.
- Manually save/load that library to GitHub using the HTTPS Contents API. GitHub tokens are kept in the operating system credential store; sync is not automatic.
- Use the 13 built-in chat providers: OpenAI, Anthropic, DeepSeek, OpenRouter, DashScope/Qwen, Moonshot/Kimi, Zhipu GLM, SiliconFlow, Groq, Gemini, llama.cpp, vLLM, and Ollama.
- Refresh available models when the provider exposes a models endpoint. Chat Endpoint remains editable; model discovery uses its own built-in endpoint or the local server address.
- Remember settings and model selections for each provider, including per-model Reasoning preferences. All 13 providers expose the Reasoning selector; **Model Default** sends no reasoning override.
- Optionally send images from a source field as Base64 image data to a vision-capable OpenAI-compatible model.
- Audio: Edge TTS plus optional local Kokoro MLX (English only); Edge voice names include region codes (for example, `US-AriaNeural`, `GB-SoniaNeural`); four independent voice blocks, uniform per-note random selection, named Audio Profiles, asynchronous synthesis, conservative Skip/Replace and Anki media references.
- Process one selected note or multiple selected notes from the Browser; Advanced has no arbitrary 100-note batch cap (preflight validation still applies).

## Requirements

- Anki 26.05 or newer is the tested target for the current release.
- Internet access is required for remote AI providers and Edge TTS.
- A compatible API key is required for paid or hosted LLM providers.
- Ollama, llama.cpp, and vLLM require a local server to be running before generation.
- Image OCR requires a vision-capable model and an endpoint that accepts OpenAI-style `image_url` message parts. Some servers expose the same model name in a text-only endpoint; in that case OCR will fail even if another UI can use a vision variant.
- Image OCR supports images stored in Anki's media folder and `data:image/...;base64,...` images. Remote image URLs are not fetched or forwarded for privacy and security. If your note contains a remote image, download it and add it to Anki media first.

## Installation

### From AnkiWeb

1. Open Anki.
2. Go to `Tools > Add-ons > Get Add-ons`.
3. Paste the AnkiWeb code for AINotePro.
4. Restart Anki.

The AnkiWeb code will be available after the add-on is published.

### From a local `.ankiaddon` file

1. Download the `.ankiaddon` package.
2. Double-click it, or use `Tools > Add-ons > Install from file`.
3. Restart Anki.

## Basic Usage

1. Open the Browse window and select one or more notes.
2. Open `AINotePro > Add Context to selected Field...`, or click the AINotePro editor toolbar button.
3. Choose the `Text` tab.
4. Select a provider, edit **Chat Endpoint** (cloud) or **Server Address** (local) as needed, enter an API key if required, and choose or type a model name.
5. Write a prompt. Use `{Source Field}` where the selected source field content should be inserted.
6. Choose the source and destination fields.
7. Click `Generate`.

### Text Advanced mode

Text also provides an **Advanced** mode for one or more existing source fields
and one or more existing destination fields on notes of the same Note Type.
Select the fields at the bottom of the Text page and use each source as
`{Field Name}`. Declare each requested result once with `{OUT:Field Name}`.
For example, `{Text}\n{OUT:Translation}\nTranslate naturally.` Advanced checks
that the selected and declared source/destination sets match before it sends a
request. **Batch Size** is a compact editable selector with dropdown choices 1–10, default 1, and manual entry of 11–99 (two digits maximum). At size 1,
Advanced uses the original single-note JSON object protocol. At sizes 2–99,
Advanced sends several notes per model request and accepts independently
validated JSONL records identified by Note ID. If 10 notes yield 8 valid
records, only the other 2 are retried; the following fresh batch again uses
the selected size. Three consecutive requests with no new valid record stop
the entire task. A confirmed context/output limit error stops immediately
and suggests lowering Batch Size. There is no automatic context detection.

Advanced never runs Image Recognition or OCR. It converts existing readable
field HTML to text, rejects empty or media-only sources for the whole batch,
and asks before replacing non-empty targets. There is no fixed 100-note limit;
all selected notes still undergo the same batch-wide preflight before requests.
Valid model outputs are held until one final Anki CollectionOp checks note
snapshots and writes fields under the existing Undo protocol. Cancel before
commit discards uncommitted outputs; a non-cancel generation failure commits
only validated outputs. Easy prompts, OCR behavior, and saved Easy prompts
remain separate from Advanced prompts. Literal prompt braces
must be escaped as `{{` and `}}`.

Before Text Easy or Audio generation, all selected notes are checked for a single **Note Type** and valid Source/Destination fields. A mixed selection is rejected before any model or TTS request or note write. Different card templates of the same Note Type are allowed; Text Advanced already performs its own full-batch validation.

For Audio (the compact Audio page has no internal scrollbar):

1. Open `Audio`, select `Edge-TTS` or `Kokoro MLX (Local)` under `Generate using`.
2. For Kokoro, run your separate local Gradio service at `http://127.0.0.1:7860`; use `Retry` if the status is unavailable. The plugin does not start Kokoro or install models.
3. Configure one to four enabled Voice blocks. Kokoro has per-block American/British accent, Female/Male, voice and speed (0.70–1.30×); Edge provides language, gender filtering, Speed, and Volume controls. Edge voice names show their region codes (for example, `US-AriaNeural` and `GB-SoniaNeural`) in the existing voice list, without adding an Accent selector. The former Pitch control is no longer shown. A different complete enabled block is chosen uniformly for each note.
4. Choose Source/Destination fields. The default policy is Skip if any sound tag already exists. `Replace managed audio only` requires a matching local provenance record and exact media hash.
5. At the bottom of the Audio page, select an existing Profile to load its complete settings immediately. If the current Profile was edited, switching offers `Save` (save the **previous** Profile), `Discard` or `Cancel`. Type a new name and click `Save` to create a Profile; `Save` with an existing name updates that Profile. `Delete` removes a saved Profile, not Anki media. There is no `Load`, New or Save As button. Generation does not save Profile edits.
6. Use the visible left/right arrow buttons beside each Speed/Volume slider to adjust by 1% (the buttons use Qt-drawn icons rather than font symbols). Click `Generate` with either saved or unsaved Audio settings. Generating never saves a Profile. Synthesis runs in the background; collection writes and media registration are handled by the Anki UI thread. Preview uses a managed Qt Multimedia player and a temporary MP3, not an Anki media file.

The Kokoro adapter currently uses Python standard-library HTTP with queue (120 s), processing + download (300 s), and overall (420 s) deadlines, not `gradio_client`. No remote service is started or required for mobile Anki playback once media sync completes.

## Prompt Templates

Prompt templates are stored in the add-on's `user_files` folder. Anki preserves this folder during add-on upgrades, so prompts and local settings are not erased when the add-on is updated.

Select a saved prompt from **Prompt Name** to load it immediately. **New** asks for a name and starts a blank, unsaved prompt; **Save** creates that new prompt or updates the selected saved prompt. **Save As** copies the current editor text to a different, new name. **Delete** removes the selected saved prompt. New, Save, Save As and Delete remain on the right.

**Import** and **Export** operate on one complete **AINotePro library** JSON (`format: AINotePro.library`, `version: 1`), containing saved Easy prompts, Advanced prompts, and all Audio Profiles with their Edge/Kokoro Voice configurations, source and destination fields. Only this unified format is supported by the new library feature. Export never includes unsaved drafts, Text Provider settings, API keys, or the machine's selected Audio Profile ID. Export to an existing filename creates a `(1)`, `(2)` copy. Import does not overwrite existing entries: the same name and contents are skipped, while name conflicts with different contents create `Name (1)`, `Name (2)` copies. New Audio Profiles receive new internal UUIDs; existing Profile IDs and the active selection are unchanged. Easy's protected Default is never overwritten, and Advanced's dynamic Default is excluded. All three domains are validated before one atomic local configuration write.

### GitHub library sync: complete setup guide (private repository recommended)

This feature stores your **saved** Easy/Advanced prompts and Audio Profiles in **one JSON file** in your GitHub repository. It does **not** upload Anki decks, notes, generated audio files, LLM settings, or API keys. Synchronization is **manual**, not automatic. You do not need to install Git, GitHub CLI, configure SSH, or use a terminal.

**Step 1 — Create a repository for your personal library.**

1. Sign in to [GitHub](https://github.com), click **+ → New repository**, or open [github.com/new](https://github.com/new).
2. Choose your account under **Owner**. For **Repository name**, you can use `anki-personal-library`. Select **Private** (recommended), since prompts or Audio Profiles may contain personal information. This must be **your own data repository**, not the `ernestyu/AINotePro` add-on source repository.
3. Select **Add a README file** to initialize the repository, then click **Create repository**. Check the actual default branch shown on GitHub (usually `main`). Existing repositories are also supported, but the selected branch must already exist.
4. For a repository URL such as `https://github.com/yourname/anki-personal-library`, AINotePro needs **only** `yourname/anki-personal-library`. Do **not** manually create `ainotepro-library.json` on GitHub; the first successful Save creates it.

**Step 2 — Create a fine-grained Personal Access Token with limited permissions.**

1. On GitHub, select your avatar → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**, or go directly to [Create a fine-grained token](https://github.com/settings/personal-access-tokens/new).
2. Enter a **Token name**, such as `AINotePro Library Sync`, and choose an **Expiration**. Once expired, you will need to generate and save a replacement token.
3. Set **Resource owner** to the account or organization that owns the repository created in Step 1. Under **Repository access**, choose **Only select repositories**, then select **only** `anki-personal-library`. Do not grant access to all repositories.
4. Under **Repository permissions**, locate **Contents** and choose **Read and write**. GitHub may add **Metadata: Read-only** automatically; this is expected. No Administration, Actions, Issues, or other write permissions are needed. To Save/Load from a private repository, use this token. Anonymous Load may work for a public repository.
5. Click **Generate token** and copy it immediately (fine-grained tokens typically start with `github_pat_`). GitHub does not display the complete token again. Do not put it into a repository, issue, screenshot, or chat. If lost, generate a replacement. An organization may require administrator approval of the token.

**Step 3 — Enter the exact settings in AINotePro.**

1. In Anki, open AINotePro → **Text**. Click the **⚙** next to **Save to GitHub** and **Load from GitHub**, opening **GitHub AINotePro Library Settings**.
2. Fill out the form (replace `yourname` with your GitHub login):

   | Field | Example | What it means |
   |---|---|---|
   | **Repository** | `yourname/anki-personal-library` | Enter `owner/repo`, **not** the full URL or a `.git` suffix |
   | **Branch** | `main` | Must be an **existing** branch; use the actual name shown on GitHub (sometimes `master`) |
   | **JSON path** | `ainotepro-library.json` | Relative path **inside the repository**, not a local file path; for example `anki/ainotepro-library.json` also works |
   | **Access token** | Paste the new `github_pat_…` token | Only required when no token is saved for this repository or when replacing it |

3. After entering Repository, allow the status to update to **Token status: Not saved for this repository**. Paste the token into **Access token**, click **OK**, then choose **Yes** in **Confirm GitHub Token Storage**. The add-on writes the token to the OS credential store and reads it back to verify. The resulting success message confirms **local token storage only**; it is **not** proof of remote GitHub access or successful upload.
4. On later visits, **Token status: Saved in system credential store** and a disabled token input are **normal**. Do not paste the token again. To rotate an expired token, click **Replace Token**, enter the new value, and confirm **OK → Yes**. To remove the saved token from this computer, check **Remove saved token for this repository** and confirm. Tokens are stored separately for each repository.
5. Secure storage uses **macOS Keychain**, **Windows Credential Manager**, or **Linux Secret Service** (with a working `secret-tool`). Tokens are not written to `user_config.json` or exported libraries. If the OS credential store is unavailable, AINotePro reports an error rather than saving plaintext.

**Step 4 — Upload the first library (Save to GitHub).**

1. First **Save** any Text prompts and Audio Profiles you intend to keep. **Unsaved drafts are not transferred**; save or discard outstanding prompt edits before syncing.
2. Click **Save to GitHub**. A successful first Save creates the JSON file at the selected Branch/JSON path. Later saves fetch the remote library first and **merge** saved local entries without overwriting existing remote entries. You do not need to edit the JSON manually.
3. Wait for **AINotePro library saved to GitHub** or **GitHub AINotePro library is already up to date**. Open the repository on GitHub, select the configured branch, and verify that the file exists at the expected path. **This is the upload verification**, not the earlier token-storage message.

**Step 5 — Restore the library on another computer (Load from GitHub).**

1. Install AINotePro in Anki on the second computer. Open the same **⚙** window and enter the **same Repository, Branch, and JSON path**.
2. For a private repository, you must **save a token on this computer as well** (the same still-valid repository-scoped token is acceptable). Tokens are **not** synchronized through the library. A public repository may allow Load without a token.
3. Click **Load from GitHub**. AINotePro **merges** remote entries into the current computer without deleting existing prompts or Audio Profiles. Same-name, different-content entries receive numbered names. Review **Prompt Name** and the **Audio Profiles** list after import.
4. Later, after changing something on computer A, use **Save to GitHub** on A and **Load from GitHub** on B. Repeat in the other direction if B also added content. This is **not real-time two-way automatic sync**.

**Troubleshooting by error stage.**

| Error / symptom | What to check |
|---|---|
| `check_repository` / HTTP 404 | Repository must be `owner/repo` rather than a URL. Confirm it exists, the token's **Resource owner** is correct, **Only select repositories** includes it, and any organization token approval is complete |
| `check_branch` / HTTP 404 | The selected branch does not exist or cannot be accessed; verify `main` versus `master` on GitHub |
| HTTP 401 / 403 | Token expired, was revoked, or lacks permissions; verify **Contents: Read and write**; use **Replace Token** if needed |
| `read_file` / HTTP 404 | After repository and branch checks pass, a missing JSON file is **normal for the first Save**; Load requires an earlier successful Save and the same JSON path |
| `create_or_update_file` / HTTP 409 / 422 | Check concurrent edits, branch protection, write access, and target file/path conflicts, then retry |
| Credential store unavailable | Check macOS Keychain, Windows Credential Manager, or the Linux Secret Service session and `secret-tool`. Do not copy the token into plaintext configuration |
| Prompt names get `(1)`, `(2)` | Same name, different content existed on different devices; numbered copies are intentional non-overwriting merge behavior |

**Diagnostics and security:** Errors report the failing stage (`check_repository`, `check_branch`, `read_file`, `create_or_update_file`), HTTP status, and GitHub Request ID. A bounded log is stored at `user_files/logs/github_sync.log` and mirrored to the terminal that launched Anki. The log includes repository/branch/path information, but never the token, Authorization headers, or library contents. Use a dedicated Private repository, least-privilege token access, and a reasonable expiration. Revoke or replace tokens at [GitHub Fine-grained tokens](https://github.com/settings/personal-access-tokens). Redact personal repository names and paths before sharing diagnostic logs publicly.

**V1 conflict contract:** synchronization preserves the *union of saved content* without overwriting existing local names, but does **not** force the same name-to-content mapping on different devices. Identically named, different-content entries gain numeric suffixes; repeated Save/Load must not create additional copies of that content in the same numbered-name family. Different names with identical text are deliberate aliases and are retained. Easy/Advanced prompts and Audio Profiles use case-insensitive, NFC-normalized name identity. Audio exports use a fixed V1 field allowlist and silently omit unknown Profile/provider/Voice properties, including accidental credential fields. Existing Text provider settings and API keys are never synchronized. These decisions are intentional and are not cross-device canonical naming guarantees.

**GitHub synchronization diagnostics:** GitHub requests check repository and branch visibility before treating a 404 on the library file as a first-time upload. The error dialog reports the failing stage (check_repository, check_branch, read_file, create_or_update_file), HTTP status, and GitHub Request ID. A bounded rotating log is stored under `user_files/logs/github_sync.log`, **and every request result is also printed in the Anki launch terminal**. Both include stage, status, GitHub Request ID, repository/branch/path and whether a token was supplied, but never the token, Authorization headers or library contents. If the log file cannot be written, the error dialog reports the logging failure instead of claiming the file was saved. For a private repository, a saved Keychain token alone does not prove that GitHub granted access: verify the fine-grained token's resource owner, selected repository, Contents permissions, and expiry. For support, share the error stage and a redacted diagnostic log, not your token.


The built-in **Default** is protected from Save, Delete and Import overwrites. You can edit it temporarily and use Save As to keep a copy. Existing customized Default text is retained; this update does not reset it. When switching away from unsaved changes, the editor offers Save / Discard / Cancel (or Discard / Cancel for Default). The Prompt Name selector is read-only; naming is handled by New and Save As.

## Provider Notes

AINotePro uses OpenAI-compatible HTTP requests for most text providers. A provider entry is a convenience preset for **Chat Endpoint**, model discovery and default model; it does not guarantee that every account, region or server exposes the same model list. In Text, the **Temperature** field is next to API Key, and the footer places the GitHub link, **Restore Default LLM Parameters**, and Help on the left; Close and Generate remain on the right. Restore affects only the selected Text provider and preserves its API key (and the current local server address).

**Reasoning:** Off, Low, Medium, High, and Model Default are selectable for every built-in provider, with preferences saved per model. **Model Default** sends no reasoning control field and uses the server default. Explicit selections send `reasoning_effort` on OpenAI-compatible Chat endpoints (Off = `none`, Low/Medium/High = `low`/`medium`/`high`); whether the backend honors it depends on its API and model. For native Ollama, Off sends `think: false` and Low/Medium/High send `think: true` without a guaranteed strength difference. Unsupported values can fail on some services; use Model Default when you do not need a manual override. A custom OpenAI-compatible NInfer server can be used through an editable Chat Endpoint even when a cloud preset is selected.

**Diagnostics:** Set `AINOTEPRO_DEBUG=1` or enable the existing debug setting to print the actual outgoing Temperature, reasoning override (or `server_default`), output-token limit (or `server_default`) and streaming flag. Request timing and token usage are logged when available. The logger does not print prompts, response bodies or API keys; server execution of a setting cannot be inferred from the request log alone.

Provider URL examples (the UI edits **Chat Endpoint**, not these base URLs, for cloud providers):

| Provider | Default Base URL | Default Model |
| --- | --- | --- |
| OpenAI | `https://api.openai.com` | `gpt-4o-mini` |
| Anthropic (Claude) | `https://api.anthropic.com` | `claude-sonnet-4-5` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| OpenRouter | `https://openrouter.ai/api` | `openai/gpt-4o-mini` |
| DashScope/Qwen | `https://dashscope.aliyuncs.com/compatible-mode` | `qwen-plus` |
| Moonshot/Kimi | `https://api.moonshot.cn` | `moonshot-v1-8k` |
| Zhipu GLM | `https://open.bigmodel.cn/api/paas` | `glm-4-flash` |
| SiliconFlow | `https://api.siliconflow.cn` | `Qwen/Qwen2.5-7B-Instruct` |
| Groq | `https://api.groq.com/openai` | `llama-3.1-8b-instant` |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.0-flash` |
| llama.cpp | `http://127.0.0.1:8080` | user-defined |
| vLLM | `http://127.0.0.1:8000` | user-defined |
| Ollama | `http://localhost:11434` | `llama3` |

If `Refresh` returns no models, type the model name manually. The Models Endpoint field is not user-editable in this UI; model refresh uses the provider's saved/built-in Models Endpoint, while llama.cpp and vLLM derive it from the current Server Address. Many OpenAI-compatible servers do not provide a complete `/models` response.

## Privacy

AINotePro sends selected note field content to the provider you configure. If image source mode is enabled, images in the source field may be read from your Anki media folder, encoded as Base64 data, and sent to the configured model endpoint. Audio generation sends selected text to the chosen Edge TTS service or to the configured local loopback Kokoro Gradio service.

Do not use the add-on with private, medical, legal, or confidential notes unless you understand and accept the privacy policy of the selected provider.

API keys and provider settings are stored locally in the add-on's `user_files/user_config.json`.

## Troubleshooting

- If no text appears in the destination field, confirm that the source field is not empty, the prompt contains `{Source Field}` or `{Source}`, and the provider returns non-empty content.
- If image OCR fails with a server error, confirm that the exact endpoint accepts image inputs, not only text chat completions.
- If image OCR reports a remote image URL, download the image and add it to Anki media first.
- If model refresh fails, type the model name manually and use `Check`.
- If audio is not appended, confirm that a voice is enabled and the destination field exists on the selected note type.
- For local providers, confirm that the local server is running and reachable from Anki.
- If Reasoning Off/Low/Medium/High fails or seems ineffective, check whether the exact server/model supports the transmitted control field, or select Model Default to omit the override. For a local NInfer OpenAI-compatible endpoint, Off sends `reasoning_effort: "none"`.
- If Audio speed/volume buttons show blank glyphs in an older version, update the add-on to the revision with Qt-drawn left/right arrows and restart Anki.

## Support

Please report bugs and feature requests on GitHub:

https://github.com/ernestyu/AINotePro/issues

When reporting a bug, include:

- Anki version and operating system.
- Provider name, Base URL, and model name. Do not include API keys.
- Whether the issue happens from the Browse menu, editor toolbar button, or both.
- The exact error message from Anki, if any.

## License

AINotePro is released under the MIT License. Vendored third-party dependencies keep their own licenses; see `THIRD_PARTY_NOTICES.md` and the metadata files in `libs/`.

## Development

The add-on entry point is `__init__.py`. The current user-facing dialog lives in `ainotepro/ainotepro_gui.py`, with tab implementations in `ainotepro/ui/text_tab.py` and `ainotepro/ui/tts_tab.py`.

Run a syntax check before packaging:

```bash
python3 -m compileall __init__.py ainotepro
```

Build a package from the add-on root:

```bash
find . -name "__pycache__" -type d -prune -exec rm -rf {} +
rm -f ../AINotePro.ankiaddon
zip -r ../AINotePro.ankiaddon * \
  -x "user_data/*" "user_files/*" "ainotepro/logs/*" "*.pyc" "*.pyo" ".git/*" "*.DS_Store" "*.bak" "meta.json"
zip -ur ../AINotePro.ankiaddon user_files/README.txt
```

The generated zip must contain `__init__.py` at the top level. Do not include the parent `AINotePro/` folder inside the archive.
