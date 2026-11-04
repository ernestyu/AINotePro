# AINotePro — AnkiWeb Description Draft

[English](ANKIWEB_DESCRIPTION.md) | [简体中文](ANKIWEB_DESCRIPTION.zh-CN.md)

AINotePro adds AI-assisted text and audio generation to Anki's Browse window and editor.

## Features

- **Text Easy:** Generate text from one source field into one destination field, with reusable prompts and optional vision/OCR input.
- **Text Advanced:** Use multiple source and destination fields, explicit `{OUT:Field Name}` declarations and strict JSON results. All selected notes undergo batch-wide preflight; there is no arbitrary 100-note limit.
- Save, reuse, import and export prompt templates. The built-in Default prompt is protected.
- Use 13 built-in text providers: OpenAI, Anthropic, DeepSeek, OpenRouter, DashScope/Qwen, Moonshot/Kimi, Zhipu GLM, SiliconFlow, Groq, Gemini, llama.cpp, vLLM and Ollama. Cloud Chat Endpoints and local Server Addresses remain editable.
- Set **Temperature** and per-model **Reasoning** (Off / Low / Medium / High / Model Default) for all 13 presets. Model Default sends no reasoning override; explicit choices depend on the model server's API support. Native Ollama has a Think on/off control without guaranteed intensity levels.
- Refresh available models where supported, or enter a model manually. The Models Endpoint remains an internal setting; the UI does not expose a separate endpoint editor.
- Generate MP3 audio with Edge TTS or optional local Kokoro MLX. Edge TTS voice choices show region codes before names (for example, `US-AriaNeural` and `GB-SoniaNeural`), making accents easier to identify. Audio provides up to three independent Voice blocks, named Profiles, background synthesis, and Speed/Volume sliders with Qt-drawn left/right adjustment arrows.
- Generate for one or multiple selected notes; apply conservative note/media write rules.

## Requirements

- Anki 26.05 or newer is the target version; available TTS voices depend on the selected service.
- Hosted providers require network access and, where applicable, your own API key.
- Local servers such as Ollama, llama.cpp, vLLM, NInfer or Kokoro must run separately.
- OCR requires an endpoint that actually supports image input. For privacy, supported sources are Anki media images and `data:image/...;base64,...`; remote image URLs are not fetched.

## Privacy

AINotePro sends the selected source text and prompts to the chosen LLM service. If image input is enabled, eligible Anki media images may be encoded as Base64 and sent to that endpoint. Audio text is sent to Edge TTS or your configured local Kokoro service. Provider settings and API keys are stored locally. Review the applicable provider policy before processing sensitive notes.

## Support

Report issues at https://github.com/ernestyu/AINotePro/issues . Include your Anki version, operating system, provider, Chat Endpoint/Server Address, model and error message. **Do not include API keys or private note contents.**
