# AINotePro

AINotePro is an Anki add-on for adding AI-generated text and audio to note fields. It can be opened from the Browse window menu or from the editor toolbar button above a note.

## Features

- Generate text from a source field and write the result to a destination field.
- Use saved prompt templates with `{Source Field}` or `{Source}` placeholders.
- Save, load, delete, import, and export prompt templates.
- Use OpenAI-compatible chat completion providers, including OpenAI, DeepSeek, OpenRouter, DashScope/Qwen, Moonshot/Kimi, Zhipu GLM, SiliconFlow, Groq, Together, Perplexity, Gemini-compatible endpoint, LM Studio, LocalAI, and Ollama.
- Refresh available models when the provider exposes a models endpoint.
- Remember the last provider settings and the last model that generated successfully.
- Optionally send images from a source field as Base64 image data to a vision-capable OpenAI-compatible model.
- Audio V2 development candidate: Edge TTS plus optional local Kokoro MLX (English only); three independent voice blocks, uniform per-note random selection, named Audio Profiles, asynchronous synthesis, conservative Skip/Replace and Anki media references. **Not yet verified in Anki.**
- Process one selected note or multiple selected notes from the Browser.

## Requirements

- Anki 26.05 or newer is the tested target for the current release.
- Internet access is required for remote AI providers and Edge TTS.
- A compatible API key is required for paid or hosted LLM providers.
- Ollama, LM Studio, and LocalAI require a local server to be running before generation.
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
4. Select a provider, enter its Base URL and API key, and choose or type a model name.
5. Write a prompt. Use `{Source Field}` where the selected source field content should be inserted.
6. Choose the source and destination fields.
7. Click `Generate`.

For Audio V2 (development candidate; no Anki integration testing has been performed):

1. Open `Audio`, select `Edge-TTS` or `Kokoro MLX (Local)` under `Generate using`.
2. For Kokoro, run your separate local Gradio service at `http://127.0.0.1:7860`; use `Retry` if the status is unavailable. The plugin does not start Kokoro or install models.
3. Configure one to three enabled Voice blocks. Kokoro has per-block American/British accent, Female/Male, voice and speed (0.70–1.30×); Edge retains its original language, volume and pitch options. A different complete enabled block is chosen uniformly for each note.
4. Choose Source/Destination fields. The default policy is Skip if any sound tag already exists. `Replace managed audio only` requires a matching local provenance record and exact media hash.
5. Use `Save`, `Save As`, `Load` or `Delete` to manage persistent Audio Profiles; simply clicking Generate does not save a Profile.
6. Click `Generate`. Synthesis runs in the background; collection writes and media registration are handled by the Anki UI thread. Preview writes a temporary MP3, not an Anki media file.

The Kokoro adapter currently uses Python standard-library HTTP to speak Gradio's queued-call API, not `gradio_client`. **This alternate transport has not been validated against the user's actual Gradio or Anki Python runtime.** The user explicitly requested no tests and no CI in this development pass; it must be verified on the Mac mini before release. No remote service is started or required for mobile Anki playback once media sync completes.

## Prompt Templates

Prompt templates are stored in the add-on's `user_files` folder. Anki preserves this folder during add-on upgrades, so prompts and local settings are not erased when the add-on is updated.

Use the prompt name field to select an existing prompt or type a new name. Selecting a prompt loads it automatically. `Save` stores the current prompt text under that name. `Delete` removes the selected template.

The `Online` prompt sharing button is currently disabled; shared prompt publishing is not implemented in this release.

## Provider Notes

AINotePro uses OpenAI-compatible HTTP requests for most text providers. A provider entry is a convenience preset for Base URL and default model; it does not guarantee that every account, region, or server exposes the same model list.

Common Base URL examples:

| Provider | Default Base URL | Default Model |
| --- | --- | --- |
| OpenAI | `https://api.openai.com` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| OpenRouter | `https://openrouter.ai/api` | `openai/gpt-4o-mini` |
| DashScope/Qwen | `https://dashscope.aliyuncs.com/compatible-mode` | `qwen-plus` |
| Moonshot/Kimi | `https://api.moonshot.cn` | `moonshot-v1-8k` |
| Zhipu GLM | `https://open.bigmodel.cn/api/paas` | `glm-4-flash` |
| SiliconFlow | `https://api.siliconflow.cn` | `Qwen/Qwen2.5-7B-Instruct` |
| Groq | `https://api.groq.com/openai` | `llama-3.1-8b-instant` |
| Together | `https://api.together.xyz` | `meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo` |
| Perplexity | `https://api.perplexity.ai` | `sonar` |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-1.5-flash` |
| LM Studio | `http://localhost:1234` | user-defined |
| LocalAI | `http://localhost:8080` | user-defined |
| Ollama | `http://localhost:11434` | `llama3` |

If `Refresh` returns no models, type the model name manually. Many OpenAI-compatible servers do not provide a complete `/models` response.

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
