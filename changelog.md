# Changelog

## Audio V2 - Development candidate (2026-10-29, not release-tested)

- Added English-only local Kokoro Gradio Provider and user-visible American/British, Female/Male voice labels with official quality metadata.
- Added versioned Audio Profiles with migration, independent Provider settings and atomic file replacement.
- Kept the three original Voice blocks, with complete per-note random Voice selection and per-block Preview.
- Moved audio synthesis off the Qt UI thread; added cancellation gate, Anki media provenance and conservative Skip/Replace.
- Disabled legacy direct audio-writing entry to prevent bypassing the V2 safety policy.
- **Per user instruction, no tests or CI were run. Anki/Gradio runtime compatibility and release acceptance remain unverified.**


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
