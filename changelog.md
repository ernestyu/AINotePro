# Changelog

[English](changelog.md) | [简体中文](changelog.zh-CN.md)

## v1.1.1 — Library synchronization and Audio updates (2026-11-05)

### Text Library

- **Full-library Import/Export:** Text Import and Export now operate on one `AINotePro.library` version 1 JSON file containing saved Easy prompts, Advanced prompts, and Audio Profiles, including all four Edge/Kokoro Voice slots. Existing local saved prompts and profiles remain in `user_files` during an add-on upgrade. The new Import accepts the unified library format, not old prompt-only export JSON.
- **Manual GitHub synchronization:** Added Save to GitHub, Load from GitHub, and repository/branch/JSON-path settings, including repository subdirectories. Uses the HTTPS Contents API; no local git, gh or SSH configuration is required. Remote and local imports are non-destructive; conflicting names gain numbered suffixes and repeated imports avoid duplicate numbered entries.
- **Secure GitHub credentials:** Fine-grained tokens are stored per repository in macOS Keychain, Windows Credential Manager, or Linux Secret Service. The UI displays saved state without revealing the token, requires confirmation to save/replace/remove it, and checks for partial changes when settings persistence fails. Tokens do not enter exported JSON or normal settings files.
- **Reliability and diagnostics:** Added credential/branch/repository preflight, conflict-aware GitHub writes, async network calls, bounded diagnostic logs, full-library validation, atomic local config updates, Audio export field allowlisting, and Unicode-safe prompt/profile name checks.

### Audio and note safety

- **Fourth Voice slot:** Increased the number of independent Voice blocks from three to four for Edge TTS and Kokoro, including migration of saved three-slot profiles.
- **Note Type preflight:** Text Easy and Audio check that all selected notes share one Note Type and that source/destination fields exist before generating or writing. Mixed Note Types reject the batch; different card templates within one Note Type are still supported.

### Compatibility and upgrades

- The GitHub sync format is `AINotePro.library` version 1; sync is manual, not automatic. Different names with identical content are retained as separate aliases; conflicting names can map differently on different devices while saved content is preserved.
- Keep the add-on's `user_files` directory during upgrades. Restart Anki after installing the new `.ankiaddon`.
- The bundled libraries and the 13 Text providers are unchanged from v1.1.0 in this release.
- **Before upgrading:** Back up `user_files`. The new Import accepts unified Library JSON, not previously exported single-prompt JSON files. Export a fresh library from v1.1.1 when moving saved prompts and Audio Profiles between computers.
- **GitHub visibility:** Save to GitHub uploads prompt text and Audio Profile settings to the repository and path you select. Do not use a public repository for private prompt content. Provider API keys and GitHub tokens are excluded.

## v1.1.0 — Text and Audio upgrades (2026-11-03)

### Text

- **Updated LLM providers:** Refreshed the built-in provider presets and endpoint configuration, with 13 supported providers covering hosted and local models.
- **Reasoning controls:** Added per-model reasoning settings (Off, Low, Medium, High, and Model Default). Model Default leaves reasoning behavior to the selected model service.
- **Multiple inputs and outputs:** Added Advanced text generation with multiple source and destination fields, explicit output declarations, and validated JSON results.

### Audio

- **Updated Edge TTS:** Upgraded the bundled `edge-tts` library from **7.0.0 to 7.3.1**. Edge voice names now show region codes (for example, `US-AriaNeural` and `GB-SoniaNeural`) to help identify accents, without changing voice selection or saved settings.
- **Improved speed and volume controls:** Removed the Pitch slider from the Audio interface and improved Speed and Volume adjustments with sliders and step buttons.
- **Local Kokoro TTS:** Added support for a separately deployed **Kokoro TTS** service, including a Kokoro MLX server running on **Mac mini M4**. AINotePro connects to the service; it does not install or run the TTS model itself.

## v1.0.0 — Initial release

- Added text generation for selected Anki notes.
- Added OpenAI-compatible provider presets for OpenAI, DeepSeek, OpenRouter, DashScope/Qwen, Moonshot/Kimi, Zhipu GLM, SiliconFlow, Groq, Together, Perplexity, Gemini-compatible endpoint, LM Studio, LocalAI, and Ollama.
- Added prompt template save, automatic load on selection, delete, import, and export.
- Added last successful model persistence.
- Added optional image-source mode for vision-capable models.
- Added audio generation with Edge TTS and Anki `[sound:...]` field insertion.
- Moved local settings and prompt templates to Anki's upgrade-safe `user_files` folder.
- Disabled prompt/response body logging by default for release privacy.
- Prevented failed text generations from writing `[Error]` text into note fields.
- Restricted image OCR file reads to Anki's media folder by default.
- Added write confirmations and undo checkpoints for multi-note or same-field generation.
- Fixed editor toolbar launch behavior.
- Fixed single-note field update behavior by applying generated results on Anki's main thread.
- Fixed audio field insertion when opened from the editor toolbar.
