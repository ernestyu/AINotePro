# AINotePro — AnkiWeb 简体中文说明草稿

[English](ANKIWEB_DESCRIPTION.md) | [简体中文](ANKIWEB_DESCRIPTION.zh-CN.md)

AINotePro 为 Anki 浏览器和笔记编辑器提供 AI 文本与语音生成工具。

## 功能

- **Text Easy：** 根据一个来源字段生成文本，并写入一个目标字段；支持复用 Prompt 和可选的视觉识别/OCR 输入。
- **Text Advanced：** 支持多个来源及目标字段，通过 `{OUT:字段名}` 定义输出，严格验证 JSON 响应。生成前统一预检所有选中笔记；不再存在固定的 100 条批次上限。
- 保存、复用、导入及导出提示词；内置 Default 提示词受到保护。
- 支持 13 个内置 Text Provider：OpenAI、Anthropic、DeepSeek、OpenRouter、DashScope/Qwen、Moonshot/Kimi、Zhipu GLM、SiliconFlow、Groq、Gemini、llama.cpp、vLLM 和 Ollama。云端 Chat Endpoint 或本地 Server Address 可编辑。
- 全部 13 个预设均可设置 **Temperature** 与按模型保存的 **Reasoning**（Off、Low、Medium、High、Model Default）。Model Default 不发送推理覆盖参数；其他档位是否有效取决于服务端接口。原生 Ollama 只保证 Think 开关，不保证三级推理强度。
- 支持模型列表 Refresh 或手动输入模型；Models Endpoint 保留为内部设置，界面不提供单独的地址编辑框。
- 支持 Edge TTS 或可选的本地 Kokoro MLX 生成 MP3。Edge TTS 音色列表在人名前显示地区代码（如 `US-AriaNeural`、`GB-SoniaNeural`），便于辨认发音地区。Audio 提供最多三个独立 Voice 区块、具名 Profile、后台合成，以及使用 Qt 绘制左右箭头的 Speed/Volume 调节按钮。
- 支持一条或多条笔记处理，并保留保守的笔记与媒体写入规则。

## 环境要求

- 目标版本为 Anki 26.05 或更新版本；可用音色取决于所选语音服务。
- 远程 Provider 需要网络及相应 API Key；Ollama、llama.cpp、vLLM、NInfer、Kokoro 等本地服务需自行启动。
- OCR 需要实际支持视觉输入的接口。为保护隐私，只支持 Anki 媒体图像和 `data:image/...;base64,...`，不自动抓取远程图片 URL。

## 隐私

AINotePro 会向选择的 LLM Endpoint 发送来源字段文本与 Prompt；开启图像输入时，可能将 Anki 媒体图像编码为 Base64 发送。Audio 会将文本发送到 Edge TTS 或配置的本地 Kokoro 服务。API Key 等配置保存在本地。处理敏感笔记前请先阅读所用服务的隐私政策。

## 支持

问题反馈：https://github.com/ernestyu/AINotePro/issues

请提供 Anki 版本、操作系统、Provider、Chat Endpoint/Server Address、模型名称和错误信息；**不要提交 API Key 或笔记隐私内容**。
