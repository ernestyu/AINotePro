# 更新日志

[English](changelog.md) | [简体中文](changelog.zh-CN.md)

## v1.1.0 — Text 与 Audio 功能升级（2026-11-03）

### Text

- **更新 LLM Provider：** 调整内置模型服务商和 API 地址配置，支持 13 个云端与本地 Provider。
- **新增推理强度控制：** 可按模型设置 Off、Low、Medium、High、Model Default；其中 Model Default 使用模型服务端自身的默认设置。
- **支持多输入、多输出：** Advanced 模式可选择多个来源字段及多个目标字段，通过明确的输出声明和 JSON 校验生成内容。

### Audio

- **升级 Edge TTS：** 内置 `edge-tts` 从 **7.0.0 升级到 7.3.1**。
- **改进 Speed 和 Volume：** 移除 Audio 界面中的 Pitch 滑杆，增强 Speed、Volume 的滑杆及增减按钮操作。
- **支持本地 Kokoro TTS：** 可连接独立部署的 **Kokoro TTS** 服务，包括运行于 **Mac mini M4** 的 Kokoro MLX 服务。插件负责调用服务，不负责安装或启动模型。

## v1.0.0 — 初始版本

- 支持为选中的 Anki 笔记生成文本，并提供多种 OpenAI-compatible Provider 预设（其中部分旧预设已在 2026-11-03 删除）。
- 支持提示词保存、选择后自动加载、删除、导入与导出。
- 保存最后成功使用的模型；支持视觉模型的图像来源模式。
- 支持 Edge TTS 音频生成，并在 Anki 字段插入 `[sound:...]`。
- 配置与提示词保存在升级时可保留的 `user_files` 文件夹。
- 默认不记录完整 Prompt 和响应，以保护隐私；失败时不把 `[Error]` 写入笔记。
- OCR 默认只允许读取 Anki 媒体目录；多笔记或同字段写入前确认并生成 Undo 检查点。
- 修复编辑器工具栏启动及单条笔记在 Anki 主线程应用结果的问题；修复从编辑器启动时的音频字段写入。
