# AINotePro - AnkiWeb Description Draft

AINotePro adds AI-assisted text generation and text-to-speech tools to Anki's Browse window and editor.

## What it does

- Generate new text from a selected source field and write it into a destination field.
- Save and reuse prompt templates with `{Source Field}` placeholders.
- Use common OpenAI-compatible providers such as OpenAI, DeepSeek, OpenRouter, DashScope/Qwen, Moonshot/Kimi, Zhipu GLM, SiliconFlow, Groq, Together, Perplexity, Gemini-compatible endpoints, LM Studio, LocalAI, and Ollama.
- Remember the last successful model so you do not need to refresh the model list every time.
- Send source-field Anki media images as Base64 image inputs to a vision-capable model for OCR-style workflows.
- Generate MP3 audio with Edge TTS and append `[sound:...]` references to the selected field.
- Process one note or multiple selected notes.

## Requirements

- Tested with Anki 26.05.
- Remote providers require network access and, where applicable, your own API key.
- Local providers such as Ollama, LM Studio, or LocalAI must be running separately.
- Image OCR requires an endpoint that truly supports image input. For privacy, AINotePro reads local image files only from Anki's media folder by default. Remote image URLs require the `Allow Remote Image URLs` option in the Text tab.

## Privacy note

AINotePro sends selected note text to the provider you configure. If image source mode is enabled, images from the selected field may be encoded as Base64 and sent to that provider. The add-on refuses to read `file://` images outside Anki's media folder by default. TTS generation sends selected text to Edge TTS. Please review your provider's privacy policy before using the add-on with sensitive notes.

## Support

Report issues here:

https://github.com/ernestyu/AINotePro/issues

Please include your Anki version, operating system, provider, Base URL, model name, and the exact error message. Do not include API keys.
