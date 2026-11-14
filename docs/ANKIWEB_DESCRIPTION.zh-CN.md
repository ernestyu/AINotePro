# AINotePro — AnkiWeb 简体中文说明草稿

[English](ANKIWEB_DESCRIPTION.md) | [简体中文](ANKIWEB_DESCRIPTION.zh-CN.md)

AINotePro 为 Anki 浏览器和笔记编辑器提供 AI 文本与语音生成工具。

## 功能

- **Text Easy：** 根据一个来源字段生成文本并写入目标字段，支持复用 Prompt。Image Recognition 不受 Provider 名称白名单限制；模型或接口明确不支持图像输入时，弹窗提示并停止剩余 OCR 请求。
- **Text Advanced（v1.2.1 源码候选版）：** 支持通过复选框选择多个来源及目标字段，通过 `{OUT:字段名}` 定义输出。Batch Size 可编辑下拉框（预设 1–10，默认 1，最大可输入 99）允许一次请求处理多条笔记，按 Note ID 验证独立 JSONL 记录，保留有效结果、仅重试缺失项；Batch Size 1 仍使用原单笔记 JSON 协议。生成前统一预检全部笔记；不存在固定的 100 条选择上限。
- 保存、复用提示词；内置 Default 提示词受到保护。
- **统一 Library 导入/导出：** 单个 JSON 文件包含 Easy、Advanced 提示词及完整 Audio Profiles；导入时保留已有本地数据。
- **GitHub 手动同步：** 通过 Save/Load 旁的 **Settings** 设置按钮管理配置，可通过 GitHub Contents API Save/Load 完整 Library，支持仓库子目录；Fine-grained Token 保存在操作系统凭据库中，不需要 Git、gh 或 SSH，也不启用自动同步。
- 支持 13 个内置 Text Provider：OpenAI、Anthropic、DeepSeek、OpenRouter、DashScope/Qwen、Moonshot/Kimi、Zhipu GLM、SiliconFlow、Groq、Gemini、llama.cpp、vLLM 和 Ollama。云端 Chat Endpoint 或本地 Server Address 可编辑。
- 全部 13 个预设均可设置 **Temperature** 与按模型保存的 **Reasoning**（Off、Low、Medium、High、Model Default）。Model Default 不发送推理覆盖参数；其他档位是否有效取决于服务端接口。原生 Ollama 只保证 Think 开关，不保证三级推理强度。
- 支持模型列表 Refresh 或手动输入模型；Models Endpoint 保留为内部设置，界面不提供单独的地址编辑框。
- 支持 Edge TTS 或可选的本地 Kokoro MLX 生成 MP3。Edge TTS 音色列表在人名前显示地区代码（如 `US-AriaNeural`、`GB-SoniaNeural`），便于辨认发音地区。Audio 提供最多四个独立 Voice 区块、具名 Profile、后台合成，以及使用 Qt 绘制左右箭头的 Speed/Volume 调节按钮。
- **批量安全检查：** Text Easy 与 Audio 在生成前检查所选笔记属于同一 Note Type，且来源及目标字段有效；不符合条件时整批停止。
- 支持一条或多条笔记处理，并保留保守的笔记与媒体写入规则。

## 环境要求

- 目标版本为 Anki 26.05 或更新版本；可用音色取决于所选语音服务。
- 远程 Provider 需要网络及相应 API Key；Ollama、llama.cpp、vLLM、NInfer、Kokoro 等本地服务需自行启动。
- OCR 需要实际支持视觉输入的接口。为保护隐私，只支持 Anki 媒体图像和 `data:image/...;base64,...`，不自动抓取远程图片 URL。

## 隐私

AINotePro 会向选择的 LLM Endpoint 发送来源字段文本与 Prompt；开启图像输入时，可能将 Anki 媒体图像编码为 Base64 发送。Audio 会将文本发送到 Edge TTS 或配置的本地 Kokoro 服务。API Key 等配置保存在本地。手动使用 GitHub Sync 时，完整 Library JSON（包含提示词内容和 Audio Profile 设置）会写入用户指定的 GitHub 仓库；公开仓库中的内容可被他人读取。GitHub Token 保存在系统凭据库，不随 Library 上传。处理敏感笔记前请先阅读所用服务的隐私政策。

## 支持

问题反馈：https://github.com/ernestyu/AINotePro/issues

请提供 Anki 版本、操作系统、Provider、Chat Endpoint/Server Address、模型名称和错误信息；**不要提交 API Key 或笔记隐私内容**。
