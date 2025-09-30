### 1\. 项目核心理念

在设计文件结构之前，我们先确立几个核心设计理念：

1.  **UI 与逻辑分离**: 用户界面 (UI) 的代码只负责展示和接收用户输入，不应包含任何业务逻辑（如调用 API）。
2.  **服务抽象化**: 无论后端是 OpenAI, Anthropic, 还是本地的 Ollama, 对于核心逻辑来说，它们都应该提供一个统一的接口。例如，所有文本生成服务都应该有一个 `generate_text(prompt)` 方法。这通过“策略模式”或“抽象基类”实现。
3.  **配置驱动**: 插件的所有行为（使用哪个模型、API 密钥、本地服务器地址等）都应该由用户配置决定，而不是硬编码在代码里。
4.  **异步处理**: AI 服务的网络请求可能会很慢，为了不冻结 Anki 的主界面，所有耗时操作都必须在后台线程中异步执行。
5.  **统一的管理者 (Manager)**: 有一个中心协调器，负责接收来自 UI 的请求，根据配置选择合适的服务，执行任务，并将结果返回给 UI。

-----

### 2\. 建议的文件目录结构

这是一个推荐的目录结构。Anki 插件本质上是一个 Python 包，所以我们会按照标准的 Python 项目结构来组织。

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

-----

### 3\. 各模块职责详解

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

### 4\. 工作流程示例 (生成图片)

1.  **用户操作**: 用户在 Anki 编辑器中点击 AINotePro 图标。
2.  **UI 响应**: `editor_button.py` 的逻辑触发，`main_dialog.py` 中的 `MainDialog` 实例被创建并显示。
3.  **用户输入**: 用户选择“图像” -\> “DALL-E”，输入 "a red apple on a book"，然后点击“生成”。
4.  **UI -\> Core**: `MainDialog` 捕获到点击事件，调用 `AIManager.generate_image_for_field(current_note, 'Front', 'a red apple on a book')`。
5.  **Core (Manager)**:
    a. `AIManager` 从 `config.manager` 获取 DALL-E 的 API 密钥等配置。
    b. `AIManager` 调用 `provider_factory.create_provider('image', 'dalle', config)`，获得一个 `DalleImageProvider` 实例。
    c. `AIManager` 创建一个 `AsyncTask`，将这个实例和 prompt 交给它，并启动线程。UI 此时可以显示“正在生成图片...”。
6.  **Core (Async Task) -\> Service**:
    a. `AsyncTask` 在后台线程中调用 `DalleImageProvider.generate()` 方法。
    b. `DalleImageProvider` 使用 `requests` 或 `openai` 库向 OpenAI API 发送请求。
7.  **Service -\> Core (Async Task)**: API 返回图片数据（二进制流）。`AsyncTask` 接收到数据后，发出一个 `task_finished` 信号，并将数据作为参数传递。
8.  **Core (Manager) -\> UI**:
    a. `AIManager` 中连接到该信号的槽函数被触发。
    b. `AIManager` 调用 `utils.add_image_to_media_collection()`，将图片数据存入 Anki 媒体库，并获得文件名（如 `paste-123.jpg`）。
    c. `AIManager` 调用 `utils.update_field_content()`，将 `<img src="paste-123.jpg">` 这段 HTML 插入到指定字段。
    d. `MainDialog` 收到任务完成的通知，关闭加载提示，并可能显示“成功！”的消息，然后关闭对话框。

这个架构将各部分职责明确分开，当你未来想增加一个新的 AI 服务时（例如，添加 Midjourney 作为图片生成器），你只需要：

1.  在 `services/image/` 目录下创建一个 `midjourney.py` 文件。
2.  在其中创建一个 `MidjourneyImageProvider` 类，并实现 `generate` 方法。
3.  更新 `provider_factory.py` 以识别 "midjourney"。
4.  在 `ui/config_dialog.py` 和 `ui/main_dialog.py` 中添加相应的选项。

核心的 `AIManager` 和 `AsyncTask` 代码完全不需要改动。这就是低耦合、高内聚设计带来的好处。