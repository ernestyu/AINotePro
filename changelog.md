# Changelog

## Audio V2 - Profile Save/Load field fix (2026-10-29)

- Scope Audio Profile optimistic concurrency to the Audio JSON domain, not the whole shared config file: Text prompt/UI changes no longer invalidate Audio Save/Load.
- Read the Audio snapshot and revision token together, preserving conflict protection when another Audio window really changed Profiles.
- Preserve saved Voice IDs and Source/Destination field names when voice discovery is offline or note fields are unavailable, avoiding false unsaved-change prompts and silent config loss.
- Kokoro Retry now probes the current URL input; trim a trailing root slash without allowing non-loopback endpoints.
- **No tests or CI were run at the user's request. Save/Load and Gradio connectivity still require Anki field verification.**

## Audio V2 - Compact Profile UI candidate (2026-10-29)

- Removed the Audio tab's nested scroll area and tightened margins, row spacing, three Voice blocks and main dialog header/footer.
- Moved Profile management below Source/Destination, directly above the dialog's Help/Close/Generate footer.
- Replaced the Profile selector with an editable saved-name list; Save creates or updates by name, Load applies an existing name explicitly, Delete removes a saved name. Removed Save As and New controls.
- Generate accepts valid unsaved settings without requiring a Profile save or load.
- Preserve Audio V2's versioned Profile storage, three Voice behavior, and Anki media safety rules.
- **Per user instruction, no tests or CI were run; layout and behavior require inspection in the user's Anki runtime.**


## Audio V2 - Static audit remediation candidate (2026-10-29)

- Addressed static audit P0-01: separated note persistence verification, undo merge and provenance outcomes; stop the batch on undo failure without misreporting a persisted note as uncommitted; mark indeterminate commits explicitly.
- Addressed P1-01: staged queue (120s), synthesis + download (300s) and total (420s) Gradio deadlines, categorized download and validation errors. Raw HTTP protocol remains unverified on the user's Gradio.
- Addressed P1-02: changed-leaf Text settings saves with conflict detection; Text prompt metadata writes use atomic shared config manager.
- Addressed P1-03: defer dialog close until the active worker returns, then finalize statistics and cleanup.
- Addressed P1-04: use Qt Multimedia completion/error events and close to manage Preview MP3 lifetime, not a fixed 120-second timer. Runtime availability unverified.
- Addressed P1-05 and P1-06: reject enabled empty Edge Voice and reject the entire batch if any enabled Kokoro Voice is unavailable; never silently change random selection weights.
- Addressed P2-01/P2-02/P2-03: explicit no-loaded-Profile selector state, transport error classification and Edge voice-list health gating.
- **Per user instruction, no tests or CI were run; independent read-only static re-audit and Mac mini Anki field testing are still required.**

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
