# 更新日志

[English](changelog.md) | [简体中文](changelog.zh-CN.md)

## v1.2.0 — Advanced 多笔记打包生成（源码版本 1.2.0，AnkiWeb 尚未发布）

- 仅 Advanced 新增紧凑、可输入的 **Batch Size** 下拉框（预设 1–10，默认 1，允许手动填写 1–99）；Easy 及其 Image Recognition 不变。
- 移除灰色 Resolve 独立控件，失效字段可从来源/目标字段下拉直接取消勾选。
- Batch Size 1 保留现有单笔记 JSON 协议；大于 1 时按 Note ID 返回 JSONL，逐条验证、接收有效结果，仅重试未完成笔记。连续三次零新结果停止整项任务，服务端明确报告上下文限制时直接停止。
- 生成阶段累计有效结果，最终经一次 Anki CollectionOp 复查字段并写入、保留 Undo；提交前取消不写入，窗口关闭不丢失已启动提交的结算。
- 增加安全的 Provider 错误分类、JSONL 大小保护、针对性单元测试及四平台自动化检查。
- Easy 的 Image Recognition 不再按 Provider 名称白名单禁用；当模型或接口明确不支持图像输入时，弹窗提示并停止剩余 OCR 请求。Advanced 仍只处理文本。
- 窗口标题统一从 `manifest.json` 读取版本，解决此前写死 `v1.0.0` 的问题；上方 Model 指模型，下方 Mode 指 Easy / Advanced 模式。**真实 Anki/Qt 与 Undo 验收仍由用户负责；合并源码不代表已发布 AnkiWeb。**

## v1.1.1 — Library 同步与 Audio 更新（2026-11-05）

### Text Library

- **统一导入/导出：** Text Import/Export 现使用单个 `AINotePro.library` v1 JSON 文件，同时保存 Easy Prompt、Advanced Prompt 与完整 Audio Profiles（包括 Edge/Kokoro 的四个 Voice 区块）。升级不会删除 `user_files` 中已有的提示词和 Profile。新版 Import 只接受统一 Library 格式，不接受旧的仅含 Prompt 的导出 JSON。
- **新增 GitHub 手动同步：** 增加 Save to GitHub、Load from GitHub 和仓库、分支、JSON 路径设置；支持仓库子目录。通过 HTTPS Contents API 工作，不需要本地安装 Git、gh 或配置 SSH。导入和同步均采用非覆盖式合并，同名不同内容追加数字后缀，重复导入避免产生新的编号副本。
- **系统凭据存储：** GitHub Fine-grained Token 按仓库保存在 macOS Keychain、Windows Credential Manager 或 Linux Secret Service 中。界面明确显示已保存状态但不显示 Token；首次保存、替换、删除均需确认；设置写入失败时尝试恢复并提示可能的部分完成。Token 不写入 Library JSON 或普通配置文件。
- **稳定性与安全性：** 增加仓库与分支预检、GitHub 文件 SHA 冲突处理、异步网络操作、限量诊断日志、三域数据校验与本地原子写入、Audio 导出字段白名单，以及 Unicode 名称一致性检查。

### Audio 与笔记写入安全

- **第四个 Voice Slot：** Edge TTS 与 Kokoro 的独立 Voice 区块由三个增至四个，已有三槽 Profile 可以迁移。
- **Note Type 整批预检：** Text Easy 和 Audio 在生成前检查所有选中笔记属于同一 Note Type，并验证 Source/Destination 字段存在；混合笔记类型时整批停止。同一 Note Type 的不同 Card Template 仍可一起处理。

### 兼容性与升级

- GitHub Library 使用 `AINotePro.library` v1 统一格式，属于**手动同步**，并非后台自动同步。不同名称、相同内容允许保留为别名；设备之间冲突名称映射可以不同，但已有内容不会因导入被覆盖。
- 升级时保留插件的 `user_files` 目录，安装新的 `.ankiaddon` 后重启 Anki。
- 相比 v1.1.0，本次未升级内置依赖，也未增加 Text Provider 数量（仍为 13 个）。
- **升级前注意：** 建议备份 `user_files`。新版 Import 只接受统一 Library JSON，不直接导入此前导出的单条 Prompt JSON。跨电脑迁移时，应使用 v1.1.1 导出完整 Library。
- **仓库可见性：** Save to GitHub 会上传提示词文本和 Audio Profile 设置。公开仓库中的这些内容可被他人读取；涉及私人内容时应使用私有仓库。Text Provider API Key 与 GitHub Token 不会随 Library 上传。

## v1.1.0 — Text 与 Audio 功能升级（2026-11-03）

### Text

- **更新 LLM Provider：** 调整内置模型服务商和 API 地址配置，支持 13 个云端与本地 Provider。
- **新增推理强度控制：** 可按模型设置 Off、Low、Medium、High、Model Default；其中 Model Default 使用模型服务端自身的默认设置。
- **支持多输入、多输出：** Advanced 模式可选择多个来源字段及多个目标字段，通过明确的输出声明和 JSON 校验生成内容。

### Audio

- **升级 Edge TTS：** 内置 `edge-tts` 从 **7.0.0 升级到 7.3.1**。音色列表在人名前显示地区代码（如 `US-AriaNeural`、`GB-SoniaNeural`），便于区分不同地区的发音，不改变音色筛选方式和已保存的配置。
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
