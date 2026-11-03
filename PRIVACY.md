# Privacy Policy

[English](PRIVACY.md) | [简体中文](PRIVACY.zh-CN.md)

AINotePro does not run its own cloud service. It sends data only to the provider endpoints you configure or to the audio generation service used by the add-on.

## Data sent for text generation

When you generate text, AINotePro sends the selected source field content and prompt text to the selected LLM provider.

## Data sent for image OCR

When image source mode is enabled, AINotePro may read an image referenced in the selected source field from Anki's media folder, encode it as Base64, and send it to the selected vision-capable LLM endpoint. It also accepts existing `data:image/...;base64,...` image data. The release build refuses to read `file://` images outside Anki's media folder, and remote image URLs are not fetched or forwarded.

## Data sent for audio generation

When you generate speech, AINotePro sends the selected source field text to **Edge TTS or your configured local Kokoro Gradio service**, depending on the selected Audio provider, and stores the resulting MP3 in your Anki media collection. A local Kokoro service runs separately; it is not started by the add-on.

## Local storage

Provider settings (including Temperature and per-model Reasoning preferences), API keys, model names, Audio Profiles, and prompt templates are stored locally in the add-on's `user_files` folder, which Anki preserves during add-on upgrades.

## Diagnostic logging

When DEBUG logging is enabled, AINotePro records request metadata such as model/provider, sanitized endpoint URL, Temperature and Reasoning request parameters, optional usage counts, and timing. The current logger does not print full prompts, generated responses, or API keys. The remote provider still receives the selected note data needed for processing.

## Sensitive data

Do not use AINotePro with sensitive notes unless you trust the configured provider and understand that provider's privacy policy and data retention practices.
