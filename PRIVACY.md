# Privacy Policy

AINotePro does not run its own cloud service. It sends data only to the provider endpoints you configure or to the TTS service used by the add-on.

## Data sent for text generation

When you generate text, AINotePro sends the selected source field content and prompt text to the selected LLM provider.

## Data sent for image OCR

When image source mode is enabled, AINotePro may read an image referenced in the selected source field from Anki's media folder, encode it as Base64, and send it to the selected vision-capable LLM endpoint. The release build refuses to read `file://` images outside Anki's media folder. Remote image URLs are disabled by default and require the `Allow Remote Image URLs` option in the Text tab.

## Data sent for TTS

When you generate speech, AINotePro sends the selected source field text to Edge TTS and stores the returned MP3 audio in your Anki media collection.

## Local storage

Provider settings, API keys, model names, and prompt templates are stored locally in the add-on's `user_files` folder, which Anki preserves during add-on upgrades.

## Sensitive data

Do not use AINotePro with sensitive notes unless you trust the configured provider and understand that provider's privacy policy and data retention practices.
