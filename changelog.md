# Changelog

[English](changelog.md) | [简体中文](changelog.zh-CN.md)

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
