# AINotePro — AnkiWeb Description Draft

[English](ANKIWEB_DESCRIPTION.md) | [简体中文](ANKIWEB_DESCRIPTION.zh-CN.md)

AINotePro adds AI-assisted text and audio generation to Anki's Browse window and editor.

## Features

- **Text Easy:** Generate text from one source field into one destination field, with reusable prompts and optional vision/OCR input.
- **Text Advanced (v1.2.0 source; AnkiWeb publication pending):** Use multiple source and destination fields and explicit `{OUT:Field Name}` declarations. A compact editable Batch Size selector (dropdown 1–10, default 1; manual entry up to 99) combines multiple notes per model request with independently validated JSONL responses. Partial valid results are retained; only missing notes are retried. Batch Size 1 uses the original single-note JSON protocol. All selected notes undergo batch-wide preflight; there is no arbitrary 100-note limit.
- Save, reuse, import and export prompt templates. The built-in Default prompt is protected.
- **Unified Library Import/Export:** Export or import Easy and Advanced prompts plus full Audio Profiles in a single JSON file; imports preserve existing local entries.
- **Manual GitHub synchronization:** Save/Load the library through the GitHub Contents API using a repository-specific fine-grained token securely stored by the operating system. Repository paths may include subdirectories; synchronization is never automatic.
- Use 13 built-in text providers: OpenAI, Anthropic, DeepSeek, OpenRouter, DashScope/Qwen, Moonshot/Kimi, Zhipu GLM, SiliconFlow, Groq, Gemini, llama.cpp, vLLM and Ollama. Cloud Chat Endpoints and local Server Addresses remain editable.
- Set **Temperature** and per-model **Reasoning** (Off / Low / Medium / High / Model Default) for all 13 presets. Model Default sends no reasoning override; explicit choices depend on the model server's API support. Native Ollama has a Think on/off control without guaranteed intensity levels.
- Refresh available models where supported, or enter a model manually. The Models Endpoint remains an internal setting; the UI does not expose a separate endpoint editor.
- Generate MP3 audio with Edge TTS or optional local Kokoro MLX. Edge TTS voice choices show region codes before names (for example, `US-AriaNeural` and `GB-SoniaNeural`), making accents easier to identify. Audio provides up to four independent Voice blocks, named Profiles, background synthesis, and Speed/Volume sliders with Qt-drawn left/right adjustment arrows.
- **Batch safety:** Text Easy and Audio verify that selected notes use one Note Type and contain the chosen source/destination fields before generation.
- Generate for one or multiple selected notes; apply conservative note/media write rules.

## Requirements

- Anki 26.05 or newer is the target version; available TTS voices depend on the selected service.
- Hosted providers require network access and, where applicable, your own API key.
- Local servers such as Ollama, llama.cpp, vLLM, NInfer or Kokoro must run separately.
- OCR requires an endpoint that actually supports image input. For privacy, supported sources are Anki media images and `data:image/...;base64,...`; remote image URLs are not fetched.

## Privacy

AINotePro sends the selected source text and prompts to the chosen LLM service. If image input is enabled, eligible Anki media images may be encoded as Base64 and sent to that endpoint. Audio text is sent to Edge TTS or your configured local Kokoro service. Provider settings and API keys are stored locally. Review the applicable provider policy before processing sensitive notes.

If you use GitHub Sync, the complete library JSON (prompts and Audio Profile settings) is stored in your selected GitHub repository. Check whether that repository is public or private and who can access it. Tokens remain in the OS credential store and are not uploaded.

## Support

Report issues at https://github.com/ernestyu/AINotePro/issues . Include your Anki version, operating system, provider, Chat Endpoint/Server Address, model and error message. **Do not include API keys or private note contents.**
