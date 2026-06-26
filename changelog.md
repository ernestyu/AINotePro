# Changelog

## 1.0.0 - Initial AnkiWeb Release Candidate

- Added text generation for selected Anki notes.
- Added OpenAI-compatible provider presets for OpenAI, DeepSeek, OpenRouter, DashScope/Qwen, Moonshot/Kimi, Zhipu GLM, SiliconFlow, Groq, Together, Perplexity, Gemini-compatible endpoint, LM Studio, LocalAI, and Ollama.
- Added prompt template save, load, delete, import, and export.
- Disabled the unfinished online prompt sharing button.
- Added last successful model persistence.
- Added optional image-source mode for vision-capable models.
- Added Edge TTS audio generation with Anki `[sound:...]` field insertion.
- Fixed editor toolbar launch behavior.
- Fixed single-note field update behavior by applying generated results on Anki's main thread.
- Fixed TTS field insertion when opened from the editor toolbar.
