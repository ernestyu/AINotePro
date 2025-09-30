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
ainotepro/
├── __init__.py                # 插件入口，注册钩子和菜单项
|
├── core/                      # 核心业务逻辑
│   ├── __init__.py
│   ├── manager.py             # 中心任务管理器 (AIManager)
│   ├── async_task.py          # 异步任务处理器 (QThread)
│   └── utils.py               # Anki 相关的辅助函数 (如添加媒体文件)
|
├── ui/                        # 所有用户界面相关代码 (PyQt)
│   ├── __init__.py
│   ├── main_dialog.py         # AI 生成的主对话框
│   ├── editor_button.py       # 在编辑器上添加按钮的逻辑
│   └── config_dialog.py       # 插件设置对话框
|
├── services/                  # 所有与第三方 AI 服务交互的模块
│   ├── __init__.py
│   ├── base.py                # 定义服务提供者的抽象基类 (非常重要!)
│   ├── provider_factory.py    # 工厂模式，根据配置创建具体服务实例
│   │
│   ├── text/                  # 文本生成服务
│   │   ├── __init__.py
│   │   ├── openai_text.py
│   │   ├── anthropic_text.py
│   │   └── ollama_text.py
│   │
│   ├── image/                 # 图像生成服务
│   │   ├── __init__.py
│   │   ├── dall_e.py
│   │   └── sd_webui.py        # 例如本地 Stable Diffusion WebUI
│   │
│   └── audio/                 # 音频生成服务
│       ├── __init__.py
│       ├── openai_tts.py
│       └── elevenlabs_tts.py
|
├── config/                    # 配置管理
│   ├── __init__.py
│   ├── manager.py             # 封装 Anki 的配置读取和写入
│   └── defaults.py            # 存储默认配置
|
├── res/                       # 静态资源
│   └── icons/
│       └── ai_icon.png        # 编辑器按钮图标
|
├── logs/                      # 日志文件目录（可选，但推荐）
│   └── ainotepro.log
|
├── manifest.json              # Anki 插件包元数据
└── config.json                # Anki 插件配置项定义
```

## 3. Backend (Add-on Logic) Deep Dive

### 各模块职责详解

#### `__init__.py` (插件入口)

  * **职责**: Anki 加载插件时执行的第一个文件。
  * **内容**:
      * 从 `ui.editor_button` 导入函数。
      * 使用 Anki 的钩子 (hook) `addHook("setupEditorButtons", add_ainotepro_button)` 将按钮添加到编辑器工具栏。
      * 创建一个菜单项，用于打开配置对话框。

#### `core/` (核心逻辑层)

  * **`manager.py`**: `AIManager` 类

      * **职责**: 业务逻辑的中心枢纽。UI 层不直接调用 `services`，而是通过 `AIManager`。
      * **方法示例**:
          * `generate_text_for_field(note, field_name, prompt)`
          * `generate_image_for_field(note, field_name, prompt)`
          * `generate_audio_for_field(note, field_name, text)`
      * **工作流程**:
        1.  接收来自 UI 的请求（例如，“为当前笔记的‘正面’字段生成一张关于‘苹果’的图片”）。
        2.  从 `config.manager` 读取当前配置，确定用户选择了哪个图片服务（如 DALL-E）。
        3.  使用 `services.provider_factory` 创建一个对应的服务实例 (`DalleProvider`)。
        4.  创建一个 `AsyncTask`，将服务实例和任务数据传给它，并启动任务。
        5.  监听 `AsyncTask` 的完成信号，获取结果后，使用 `utils.py` 中的函数将媒体文件写入 Anki 并更新字段。

  * **`async_task.py`**: `AsyncTask(QThread)`

      * **职责**: 在后台线程中执行耗时操作（如 API 请求），避免 UI 卡死。
      * **实现**: 继承 PyQt 的 `QThread`。在 `run()` 方法中执行实际的 AI 服务调用。通过信号/槽机制 (`pyqtSignal`) 将结果（或错误信息）传回主线程。

  * **`utils.py`**:

      * **职责**: 提供与 Anki 交互的原子操作。
      * **函数示例**:
          * `add_image_to_media_collection(image_data)`: 保存图片到 Anki 的 `collection.media` 目录并返回文件名。
          * `add_audio_to_media_collection(audio_data)`: 同上。
          * `update_field_content(note, field_name, content)`: 安全地更新卡片字段内容。

#### `services/` (服务提供者层)

这是实现插件可扩展性的关键。

  * **`base.py`**:

      * **职责**: 定义所有服务提供者必须遵守的“契约”（接口）。
      * **实现**: 使用 Python 的 `abc` 模块定义抽象基类。
        ```python
        from abc import ABC, abstractmethod

        class TextProvider(ABC):
            @abstractmethod
            def generate(self, prompt: str, config: dict) -> str:
                pass

        class ImageProvider(ABC):
            @abstractmethod
            def generate(self, prompt: str, config: dict) -> bytes: # 返回图片二进制数据
                pass

        class AudioProvider(ABC):
            @abstractmethod
            def generate(self, text: str, config: dict) -> bytes: # 返回音频二进制数据
                pass
        ```

  * **`provider_factory.py`**:

      * **职责**: 根据配置动态创建服务实例。
      * **函数示例**: `create_provider(service_type: str, provider_name: str, config: dict)`
          * 如果 `service_type` 是 "text"，`provider_name` 是 "openai"，它就会 `from .text.openai_text import OpenAITextProvider` 并返回一个 `OpenAITextProvider` 的实例。

  * **子目录 (`text/`, `image/`, `audio/`)**:

      * 每个文件实现一个具体服务，继承自 `base.py` 中对应的抽象类。
      * 例如，`ollama_text.py` 中的 `OllamaTextProvider` 会实现 `generate` 方法，其内部逻辑是使用 `requests` 库向本地 Ollama API 发送请求。

#### `ui/` (用户界面层)

  * **`editor_button.py`**:

      * 包含一个函数 `add_ainotepro_button(buttons, editor)`，它会创建一个 `QAction` 或 `QPushButton`，并将其添加到编辑器的工具栏 `buttons` 列表中。
      * 按钮的点击事件会连接到 `main_dialog.py` 中用于显示主窗口的函数。

  * **`main_dialog.py`**: `MainDialog(QDialog)`

      * **职责**: 提供一个统一的、多模态的输入界面。
      * **UI 组件**:
          * 一个下拉菜单选择服务类型（文本、图像、音频）。
          * 一个下拉菜单根据类型选择具体的服务提供者（如 OpenAI, Ollama）。
          * 一个大的 `QTextEdit` 用于输入 Prompt。
          * 一个 "Generate" 按钮。
          * 一个状态栏或标签，用于显示“生成中...”或错误信息。
      * **逻辑**:
          * 当用户点击 "Generate" 时，它会收集所有信息（服务类型、提供者、Prompt、当前笔记和字段），然后调用 `core.manager.AIManager` 的相应方法来处理请求。它**不直接调用 API**。

  * **`config_dialog.py`**: `ConfigDialog(QDialog)`

      * **职责**: 提供一个图形界面让用户输入 API 密钥、选择模型、设置本地服务器地址等。
      * **逻辑**: 保存设置时，调用 `config.manager` 中的函数将配置写入 Anki 的配置文件系统。

#### `config/` (配置层)

  * **`manager.py`**:

      * **职责**: 封装 Anki 的配置 API，为插件的其他部分提供简单的接口。
      * **实现**: 使用 `aqt.mw.addonManager.getConfig(__name__)` 和 `aqt.mw.addonManager.writeConfig(__name__, data)`。
      * **函数**: `get_config()`, `save_config(data)`, `get_provider_config('openai')`。

  * **`defaults.py`**:

      * 只包含一个 Python 字典，定义了所有配置项的默认值。当用户第一次使用插件时，会加载这些默认值。

-----

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
