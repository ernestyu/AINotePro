# AINotePro

[English](README.md) | [简体中文](README.zh-CN.md)

AINotePro is an Anki add-on for adding AI-generated text and audio to note fields. It can be opened from the Browse window menu or from the editor toolbar button above a note.

## Features

- Generate text in **Easy** mode (single source/destination) or **Advanced** mode (multiple source/destination fields with strict JSON output).
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
request. It accepts only a JSON object containing exactly the selected target
field names.

Advanced never runs Image Recognition or OCR. It converts existing readable
field HTML to text, rejects empty or media-only sources for the whole batch,
and asks before replacing non-empty targets. There is no fixed 100-note limit;
all selected notes still undergo the same batch-wide preflight before requests. Easy prompts, OCR behavior, and
saved Easy prompts remain separate from Advanced prompts. Literal prompt braces
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

**Save to GitHub**, **Load from GitHub**, and the adjacent **⚙ settings** control use the same complete library in one `ainotepro-library.json` (configurable path). Configure `owner/repo`, existing branch (default `main`), and JSON path. GitHub connection uses the HTTPS Contents API; **git**, **gh**, and SSH are not required. A fine-grained token scoped to the repository with **Contents: Read and write** is required for Save; public Load may work without a token. The token persists per repository in the operating system credential store (macOS Keychain, Windows Credential Manager, or Linux Secret Service with `secret-tool`). It survives Anki restarts but is never written to `user_config.json`, exported libraries, or process arguments. A saved token is shown by a disabled input and an explicit saved-status label; use **Replace Token** to unlock editing or the removal checkbox to delete it. Saving/replacing/removing requires a confirmation dialog. A successful save is verified by reading it back from the system credential store and acknowledged with a message. When secure storage is unavailable, the plugin reports an error rather than saving plaintext. JSON paths may include repository subdirectories, for example `anki/ainotepro-library.json`. Save merges local items into the remote library, Load merges remote items locally, and neither deletes saved data. Both preserve differently configured Audio Profiles under numbered names. Network requests run off the UI thread. Save any unsaved Text prompt or Audio Profile before transfers. After import, the Audio tab refreshes its Profile list and provider availability checks; an unavailable Edge voice or Kokoro server does not erase the saved Profile. No automatic sync is enabled.

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
