# 隐私政策

[English](PRIVACY.md) | [简体中文](PRIVACY.zh-CN.md)

AINotePro 不运行自有云端服务。它将处理所需的数据发送至用户配置的文本 Provider Endpoint 或所使用的音频生成服务。

## 文本生成时发送的数据

生成文本时，插件将选中的来源字段内容和 Prompt 文本发送至所选 LLM Provider。Text 的 Temperature、Reasoning 等请求设置也可能一起发送。**Model Default** 不发送推理覆盖字段。

## 图像识别时发送的数据

启用图像来源模式后，AINotePro 可能读取笔记字段中引用的 Anki 媒体目录图像，将其编码为 Base64，并发送至配置的视觉模型 Endpoint。它也接受已有的 `data:image/...;base64,...` 数据。

插件默认拒绝读取 Anki 媒体目录外的 `file://` 图像，也不会自动下载或转发远程图像 URL。

## 语音生成时发送的数据

生成语音时，根据选择的 Audio Provider，AINotePro 会将来源字段文本发送至 **Edge TTS** 或用户自行配置的**本地 Kokoro Gradio 服务**。得到的 MP3 会存入 Anki 媒体库。AINotePro 不会自行启动本地 Kokoro 服务。

## 本地保存的数据

Provider 配置（包含 Temperature 及按模型保存的 Reasoning）、API Key、模型名称、Audio Profile 与 Prompt 模板等保存在插件的 `user_files` 目录。Anki 升级插件时会保留该目录。

## 可选的 GitHub Library 手动同步

只有在用户主动点击 **Save to GitHub** 时，AINotePro 才通过 GitHub HTTPS Contents API 将一个完整 Library JSON 写入所设置的仓库、分支和路径。文件包含已保存的 Easy/Advanced Prompt 文本与 Audio Profile 设置（Voice、Provider、来源/目标字段名称、Kokoro 本地服务地址等）。**有权限读取该仓库的其他人也能读取这些内容；如果仓库是公开的，任何人都可以查看。** **Load from GitHub** 则读取此 JSON 并与本地数据合并。此功能不做后台自动同步。

Library 不包含 Text Provider 的 API Key 和配置、GitHub Token、未保存的草稿、Audio Profile 的本地 UUID 或当前选中项。GitHub Fine-grained Token 按仓库存入操作系统凭据库（macOS Keychain、Windows Credential Manager 或 Linux Secret Service），不写入 Library 或 `user_config.json`。进行需要身份验证的 HTTPS 请求时，GitHub 会收到相应的认证凭据。

GitHub 同步日志位于 `user_files/logs/github_sync.log`，并同步输出到启动 Anki 的终端，记录操作阶段、HTTP 状态、GitHub Request ID、仓库/分支/路径以及是否提供 Token；不会主动记录 Token 值、Authorization 请求头或 Library 内容。仓库名称与路径本身也可能透露信息，公开日志前应检查并脱敏。

## 诊断日志

启用 DEBUG 后，插件记录 Provider、模型、经过脱敏的 Endpoint URL、实际发出的 Temperature 与 Reasoning 请求参数、可获取的 Token 统计及耗时等元数据。目前的日志实现不打印完整 Prompt、生成响应或 API Key。

日志不影响外部服务接收处理所需的笔记字段数据；请依据实际使用的服务判断是否适合处理敏感信息。

## 敏感信息

如果不信任所使用的服务或不了解其隐私及数据保留政策，请勿使用 AINotePro 处理隐私、医疗、法律或其他保密笔记。
