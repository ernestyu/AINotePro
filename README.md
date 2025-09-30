# AINotePro: Your All-in-One AI Assistant for Anki

## 1. Project Overview

**AINotePro** is a powerful, multi-modal Anki add-on designed to seamlessly integrate advanced AI capabilities directly into your note creation and editing workflow. It acts as a versatile assistant, allowing you to generate text, images, and audio from various AI services, all within a unified and intuitive interface inside the Anki browser.

The project is built with flexibility and extensibility in mind, supporting both popular commercial APIs and local, self-hosted models.

### Core Features
*   **Multi-Modal Generation**: A single tool to handle Text, Text-to-Speech (TTS), and Image generation for your Anki notes.
*   **Flexible AI Service Integration**:
    *   **Text**: Natively supports any OpenAI-compatible API (e.g., OpenAI, DeepSeek, Groq, Moonshot) and local models via Ollama.
    *   **Image**: Supports services like Pollinations.ai for creative image generation.
    *   **Audio**: Integrates with services like Edge-TTS for high-quality speech synthesis.
*   **Advanced Text Generation**:
    *   Map generation from any source field to any destination field.
    *   Full control over prompts, with a built-in prompt management system (save, load, delete).
    *   Adjustable creativity via a temperature slider.
*   **Vision-Powered Content Creation**: Can analyze an image within a note field, upload it to a configured image host, and use a vision-capable model to generate a description, analysis, or any other text-based content.
*   **Integrated & Modular UI**: A clean, tabbed dialog accessible from the Anki browser provides a central hub for all AI operations.
*   **Persistent & Centralized Configuration**: Utilizes Anki's native add-on configuration system (`config.json`) to manage all user settings, including API endpoints, keys, and saved prompts, allowing for easy editing via Anki's standard configuration dialog.

### Technology Stack
*   **Core Framework**: Anki Add-on SDK
*   **UI Toolkit**: PyQt (via Anki's `aqt.qt` wrapper)
*   **Language**: Python 3.9+
*   **Networking**: `requests` (for robust API communication)
*   **Key Libraries**: `openai` (for vision models)
*   **Architecture**: A clean, layered architecture separating UI (`gui`), business logic (`logic`), and API communication (`core`).

## 2. Project Structure

The project follows a modern, layered structure that is standard for professional Anki add-ons, ensuring maintainability and ease of extension.

```
AINotePro/
├─ ainotepro/                # Main source code package
│  ├─ __init__.py           # Add-on entry point: creates menus and hooks into Anki
│  ├─ config.py             # Manages all user settings via Anki's config system
│  ├─ core/                 # API Client Layer: Handles direct communication with external APIs
│  │  ├─ text/
│  │  │  ├─ base_client.py
│  │  │  ├─ openai_client.py
│  │  │  └─ ollama_client.py
│  │  └─ image/
│  ├─ logic/                # Business Logic Layer (Services)
│  │  └─ text_service.py     # Encapsulates the logic for text generation
│  └─ gui/                  # UI Layer
│     ├─ main_dialog.py      # The main tabbed dialog window
│     ├─ text_tab.py         # UI and event handling for the "Text" tab
│     ├─ image_tab.py        # UI for the "Images" tab
│     ├─ tts_tab.py          # UI for the "TTS" tab
│     └─ components/
│        └─ model_config_gui.py # Reusable UI component for model configuration
├─ user_data/                # Stores user-specific data like image hosting configs
├─ libs/                     # Bundled third-party libraries
├─ manifest.json             # Add-on manifest for Anki 2.1.50+
├─ config.json               # Default user configuration file
└─ README.md                 # This documentation
```

## 3. Backend (Add-on Logic) Deep Dive

### Configuration and Initialization
*   **Centralized Configuration (`config.py`)**: The add-on abandons scattered JSON files in favor of Anki's official `mw.addonManager.getConfig()` and `writeConfig()`. This provides a single source of truth (`config.json`) for all settings, including model endpoints, API keys, and saved prompts. It also allows users to edit settings directly from Anki's add-on configuration screen.
*   **Entry Point (`__init__.py`)**: This file acts as the sole "plug" into Anki. It uses Anki's hook system (`addHook`) to add a "AI Note Pro..." menu item to the browser's "Edit" menu. It is responsible only for initializing and displaying the main dialog, keeping the core logic decoupled from Anki's UI.

### Core Workflow: Text Generation

The text generation process is a prime example of the project's layered architecture.

1.  **User Interaction (GUI Layer - `gui/text_tab.py`)**:
    *   The user selects a service (e.g., "DeepSeek"), chooses a model, writes a prompt, and selects source/destination fields.
    *   When the "Generate" button is clicked, the `on_generate_text` method gathers all the necessary information from the UI widgets (API key, base URL, model name, temperature, prompt, etc.).
    *   Crucially, the UI layer does **not** know how to talk to DeepSeek or Ollama. It simply packages the configuration and user input.

2.  **Business Logic (Logic Layer - `logic/text_service.py`)**:
    *   The UI layer calls `text_service.generate_text()`, passing the service name ("DeepSeek") and the configuration dictionary.
    *   The `TextGenerationService` acts as a dispatcher. Its internal `_get_client` factory method inspects the `service_name`.
    *   Since "DeepSeek" is OpenAI-compatible, the factory instantiates and returns an `OpenAIClient` object, initialized with the user's base URL and API key. If the service were "Ollama", it would return an `OllamaClient`.

3.  **API Communication (Core Layer - `core/text/openai_client.py`)**:
    *   The `text_service` then calls the `generate_chat` method on the returned client instance.
    *   The `OpenAIClient` is a "pure" class. Its only responsibility is to construct the correct JSON payload and headers for the OpenAI Chat Completions API specification.
    *   It uses the `requests` library to make the HTTP POST request, handles timeouts, and checks for HTTP errors.
    *   Upon receiving a successful response, it parses the JSON, extracts the generated text from `choices[0].message.content`, and returns it as a simple string.
    *   If any network or parsing error occurs, it raises a specific exception (e.g., `ConnectionError`, `ValueError`), which is caught by the UI layer to display a user-friendly warning.

4.  **Result Handling (GUI Layer - `gui/text_tab.py`)**:
    *   The UI layer receives the generated string (or an error message) from the service.
    *   It then updates the destination field of the current Anki note and instructs Anki to save the changes (`note.col.update_note(note)`).

This separation of concerns makes the system extremely robust and extensible. To add a new OpenAI-compatible provider, no new files are needed; one only needs to add its name to the dropdown in the UI.

### Vision Workflow: Image-to-Text

1.  **Image Detection and Upload**: When "Enable Image Source" is checked, the `on_generate_text` method finds the `<img>` tag in the source field.
2.  It uses Anki's API (`mw.col.media.dir()`) to locate the image file in the `collection.media` folder.
3.  The image is then uploaded to a user-configured image hosting platform (e.g., PStorage) via the `upload_to_img_hosting` utility, which returns a public URL.
4.  **API Call**: The `generate_with_img` function is called, passing the image URL and the user's prompt to a vision-capable model API (e.g., Claude 3, GPT-4 Vision).
5.  The returned text is then placed in the destination field, completing the image-to-text workflow.

## 4. How to Run & Develop

As this is an Anki add-on, it is run by placing the `AINotePro` folder inside your Anki `addons21` directory.

### Prerequisites
*   Anki 2.1.49+
*   Python 3.9+ (typically bundled with Anki)

### Development Setup
1.  **Locate your Anki `addons21` folder**. You can find this from within Anki by going to `Tools > Add-ons > View Files`.
2.  **Clone the repository** directly into this folder:
    ```bash
    cd /path/to/your/addons21
    git clone https://github.com/ernestyu/AINotePro.git
    ```
3.  **Install Dependencies (if any)**: If the add-on requires external Python libraries not bundled in `libs/`, you would install them into a virtual environment and copy them. For this project, most dependencies are intended to be bundled.
4.  **Restart Anki**: Anki will load the add-on on startup.
5.  **Access the Tool**: Open the Anki Browser, select one or more notes, and go to `Edit > AI Note Pro...` to open the main dialog.

### Making Changes
*   You can edit the Python files directly in the `AINotePro/ainotepro/` directory.
*   To see your changes, you must restart Anki.
*   For faster development, you can use an external IDE like VS Code or PyCharm and configure it to recognize Anki's bundled Python environment for features like code completion.

## 5. Future Roadmap & Extension Suggestions

*   **Asynchronous Operations**: For long-running AI generations, implement `aqt.task.run_in_background` to prevent the Anki UI from freezing. This would involve moving the core service calls into background threads and using a callback to update the UI upon completion.
*   **Full GUI/Logic Separation for All Tabs**: Apply the same layered architecture (GUI, Logic, Core) to the "Images" and "TTS" tabs to further improve code structure and maintainability.
*   **Unit Testing**: Add unit tests for the `logic` and `core` layers. These pure Python modules can be tested independently of the Anki environment, ensuring their reliability.
*   **Advanced Prompt Templating**: Allow users to create and manage more complex prompt templates with multiple placeholders, not just `{Source Field}`.
*   **Configuration Profiles**: Allow users to save and load entire configuration "profiles" (e.g., a "Translation Profile" with specific models and prompts vs. a "Summarization Profile").

```

<!--
[PROMPT_SUGGESTION]Please apply the proposed directory structure changes (renaming `ui` to `gui`, `services` to `logic`, etc.) to the project.[/PROMPT_SUGGESTION]
[PROMPT_SUGGESTION]Now, refactor the image generation and TTS features to follow the same layered architecture as the text generation feature.[/PROMPT_SUGGESTION]
