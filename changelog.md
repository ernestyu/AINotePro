# Changelog

## 1.0.0 - Initial AnkiWeb Release Candidate

- Added text generation for selected Anki notes.
- Added OpenAI-compatible provider presets for OpenAI, DeepSeek, OpenRouter, DashScope/Qwen, Moonshot/Kimi, Zhipu GLM, SiliconFlow, Groq, Together, Perplexity, Gemini-compatible endpoint, LM Studio, LocalAI, and Ollama.
- Added prompt template save, automatic load on selection, delete, import, and export.
- Disabled the unfinished online prompt sharing button.
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
