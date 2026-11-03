# AINotePro

[English](README.md) | [简体中文](README.zh-CN.md)

AINotePro 是一款 Anki 插件，可根据笔记字段内容生成 AI 文本或语音，并写入指定字段。可从浏览器（Browse）菜单或笔记编辑器工具栏打开。

## 功能

- **Text Easy**：从一个来源字段生成文本，写入一个目标字段；支持已保存的提示词和可选图像识别。
- **Text Advanced**：支持多个来源字段及多个目标字段，以严格 JSON 格式返回结果；生成前对整批笔记统一验证。
- 保存、加载、删除、导入和导出提示词；支持受保护的内置 Default 提示词。
- 13 个内置文本 Provider：OpenAI、Anthropic、DeepSeek、OpenRouter、DashScope/Qwen、Moonshot/Kimi、Zhipu GLM、SiliconFlow、Groq、Gemini、llama.cpp、vLLM 和 Ollama。
- 支持模型列表 Refresh（服务端需提供模型枚举接口）、手动输入模型名称，以及按 Provider 保存模型和配置。
- **Reasoning 对全部 13 个 Provider 开放**，按模型保存 Off、Low、Medium、High 或 Model Default。
- Audio：Edge TTS 和可选本地 Kokoro MLX；三个独立 Voice 区块、Audio Profile、每条笔记随机选择已启用 Voice、异步合成与受控音频写入。
- 浏览器可选择一条或多条笔记处理。Advanced **没有固定的每批 100 条上限**，但仍对全部选中笔记执行预检。

## 环境要求

- 当前版本以 Anki 26.05 或更新版本为目标；不同平台及版本仍应在实机验证。
- 远程 LLM 和 Edge TTS 需要网络连接；部分服务需要自己的 API Key。
- 本地 Ollama、llama.cpp、vLLM 或 NInfer 必须提前独立启动；AINotePro 不负责部署服务。
- OCR 需要实际支持 OpenAI 风格 `image_url` 消息的视觉模型接口。即使模型名称相同，不同服务端入口也可能只提供文本能力。
- OCR 读取 Anki 媒体目录中的图像或 `data:image/...;base64,...`；不自动下载远程图片。远程图片应先加入 Anki 媒体库。

## 安装

**AnkiWeb：** Anki → `Tools > Add-ons > Get Add-ons` → 输入插件代码 → 重启 Anki。正式发布后才会提供 AnkiWeb 代码。

**本地文件：** 下载 `.ankiaddon`，双击安装，或通过 `Tools > Add-ons > Install from file` 安装，然后重启 Anki。

## Text 使用方法

1. 在 Browse 中选中笔记，从 `AINotePro > Add Context to selected Field...` 或编辑器工具栏打开插件。
2. 选择 **Text** 标签。
3. 选择 Provider；根据需要设置云服务的 **Chat Endpoint** 或本地服务的 **Server Address**，输入 API Key 和模型名称。
4. 编辑 Prompt，选择来源和目标字段。Easy 可以使用 `{Source Field}` 或 `{Source}`。
5. 需要时设置 **Temperature** 和 **Reasoning**，点击 **Generate**。

### Advanced 模式

Advanced 支持来自同一 Note Type 的多个来源字段、多个目标字段。Prompt 使用 `{字段名}` 读取来源字段，并使用 `{OUT:字段名}` 定义每个目标字段，例如：

```text
{Text}
{OUT:Translation} Translate naturally.
```

来源/目标选择必须与 Prompt 声明双向一致。返回内容必须是 JSON 对象，键名与选中的目标字段完全一致。所有笔记在请求前经过统一预检：字段定义、来源文本是否为空或仅有媒体内容等；任意笔记不合格时整批拒绝。写入非空目标字段前会询问确认。

Advanced 不进行 OCR；Easy 和 Advanced 的提示词分别保存。Prompt 中需要字面花括号时使用 `{{` 和 `}}` 转义。**不存在固定的每批 100 条笔记限制**；选中更多笔记意味着更长的运行时间，原有进度、取消、校验和写入流程保持不变。

### 提示词管理

在 **Prompt Name** 中选择已保存的提示词即可加载。**New** 新建未保存草稿；**Save** 新建或更新当前提示词；**Save As** 另存新名称；**Delete** 删除选中的已保存提示词。Import/Export 保留。

内置 **Default** 不能直接覆盖、删除或经 Import 覆盖，但可以临时修改并通过 Save As 保存副本。切换有未保存修改的提示词时，会按情况出现 Save / Discard / Cancel。提示词及配置保存在升级时保留的 `user_files` 中。

## Provider、Reasoning 与 Temperature

大多数文本 Provider 使用 OpenAI-compatible Chat Completions 接口。预设仅提供便捷的默认接口和模型，不保证所有模型或账号的 API 能力相同。

**Reasoning：** 所有 13 个 Provider 都可以选择 Off、Low、Medium、High 和 **Model Default**，并分别保存当前模型的选择。

- **Model Default**：不发送覆盖服务器推理设置的字段，由服务器默认行为决定。不同平台兼容性不确定时应使用此选项。
- **Off / Low / Medium / High**：OpenAI-compatible 请求分别发送 `reasoning_effort: none / low / medium / high`。例如通过 DeepSeek 预设连接自定义 NInfer Endpoint 时，Off 会发送 `reasoning_effort: "none"`，以请求关闭 Thinking。服务器是否接受及执行取决于实际接口和模型；不支持的参数可能返回错误。
- **原生 Ollama**：Off 发送 `think: false`；Low、Medium、High 发送 `think: true`，**不保证存在三级强度差异**。
- **Temperature** 位于 API Key 右侧。插件将当前值写入请求，但具体模型是否采用该设置由服务端决定。

**调试日志：** 使用 `AINOTEPRO_DEBUG=1` 或已有 DEBUG 配置，可显示实际发出的 Temperature、Reasoning 参数（或 `server_default`）、最大输出 Token 是否设置、Stream、请求耗时与 API 提供的 Token 用量。不会打印 API Key、完整 Prompt 或完整响应。请求中存在参数不等于服务端保证执行。

**模型列表：** 点击 Refresh 从 Provider 的 Models Endpoint 查询；此界面不提供可编辑的 Models Endpoint 输入框。云端使用已保存或内置的模型列表地址；llama.cpp、vLLM 从当前 Server Address 推导 Chat 和 Models 路由。查询失败时可以手动输入模型名称并点击 Check。

默认服务商示例见 [英文 README 的 Provider 表](README.md#provider-notes)。自建 OpenAI-compatible 服务可通过可编辑的 Chat Endpoint 接入，不需要改变模型文件。

### Text 底部按钮

左侧从左到右为 **Enjoying AINotePro? Star it on GitHub → Restore Default LLM Parameters → Help**；右侧保持 **Close → Generate**。Restore 只恢复当前 Text Provider 的 LLM 参数；**保留 API Key**，本地 Provider 也保留当前服务器地址。Audio 标签不显示 Restore。

## Audio 使用方法

1. 选择 **Audio**，在 **Generate using** 选择 **Edge-TTS** 或 **Kokoro MLX (Local)**。Kokoro 需要自行启动本地 Gradio 服务，默认地址 `http://127.0.0.1:7860`；不可用时使用 Retry。
2. 配置最多三个 Voice 区块。Kokoro 提供美式/英式口音、Female/Male、Voice 和速度（0.70–1.30 倍）；Edge 提供语言、Speed 和 Volume 调节，界面已移除原有 Pitch 控件。每条笔记从完整启用的 Voice 区块中等概率选择一个。
3. Speed、Volume 滑杆两端用 **Qt 绘制的左/右箭头按钮**调节，每次调整 1%。Kokoro 不支持的 Volume 控件仍保持原有禁用规则。
4. 选择 Source/Destination。默认遇到已有声音标签时跳过；Replace managed audio only 需要匹配本地来源记录及媒体哈希。
5. 选择现有 Audio Profile 即立即加载其设置。有未保存更改时，切换会要求 Save / Discard / Cancel；Save 保存的是此前 Profile。新名称可用 Save 创建，Delete 只删除 Profile，不删除音频文件。Generate 可以使用未保存设置，不会自动保存 Profile。
6. 预览使用 Qt Multimedia 和临时 MP3；语音在后台合成，Anki 媒体注册与集合写入由 UI 线程处理。

Kokoro HTTP 适配器采用标准库请求，等待队列 120 秒、处理与下载 300 秒、总计 420 秒的时间限制。生成后的音频一旦同步到 Anki 媒体库，移动端播放不需要连接原 TTS 服务。

## 隐私

文本生成会向选定的 LLM Endpoint 发送 Prompt 和所选来源字段；OCR 可能将 Anki 媒体图像编码后发送给视觉模型。Audio 会向 Edge TTS 或配置的本地 Kokoro 服务发送所选文本。API Key、模型及相关设置保存在本地 `user_files/user_config.json`。

如笔记包含医疗、法律或其他保密信息，应先了解所用服务的隐私政策。完整说明见 [隐私政策](PRIVACY.md)。

## 故障排查

- 文本没有写入：检查来源字段、Prompt 占位符、目标字段以及模型是否返回有效内容。
- OCR 失败：确认实际 Chat Endpoint 支持视觉输入；远程图片请先添加到 Anki 媒体库。
- Refresh 失败：手动填写模型，并使用 Check 验证连接。
- Reasoning 失败或似乎无效：确认目标模型/API 是否支持传入字段；无须强制控制时选择 Model Default。
- 本地 Provider 失败：确认模型服务器正在运行且 Anki 能访问其地址。
- Audio 未生成：确认 Voice 已启用且来源/目标字段存在。
- 旧版本 Audio 按钮显示为空白：更新到使用 Qt 标准箭头图标的版本并重启 Anki。

## 反馈与开发

问题和功能建议：[GitHub Issues](https://github.com/ernestyu/AINotePro/issues)。报告时提供 Anki 版本、操作系统、Provider、接口地址、模型名和错误信息；**不要提交 API Key**。

代码入口为 `__init__.py`，主窗口 `ainotepro/ainotepro_gui.py`，Text 和 Audio 分别位于 `ainotepro/ui/text_tab.py` 与 `ainotepro/ui/tts_tab.py`。

打包前可运行：

```bash
python3 -m compileall __init__.py ainotepro
```

`.ankiaddon` 压缩包顶层应直接包含 `__init__.py`，不得多包一层 `AINotePro/`；打包步骤见 [英文 README](README.md#development) 和 [发布检查表](docs/RELEASE_CHECKLIST.md)。

## 许可

AINotePro 使用 MIT License。第三方依赖保留各自许可证，参见 `THIRD_PARTY_NOTICES.md`。
