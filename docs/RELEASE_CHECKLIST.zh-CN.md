# AINotePro 发布检查表

[English](RELEASE_CHECKLIST.md) | [简体中文](RELEASE_CHECKLIST.zh-CN.md)

本检查表用于发布新的 `.ankiaddon` 到 AnkiWeb 前的验证。以下为**待执行项目**，不是本次文档更新已完成的测试报告。

## 1. 发布前功能检查

- 启用插件并启动 Anki，确认没有启动异常。
- 从 Browse 菜单及笔记编辑器工具栏打开 AINotePro。
- 选择一条笔记生成 Text，确认输出写入目标字段；再验证选择多条笔记时的生成与写入。
- 在 Advanced 中验证来源/目标字段与 `{OUT:字段名}` 声明、严格 JSON 格式以及整批预检。选中**超过 100 条有效笔记**时，不应再因固定条数限制拒绝；不合格笔记仍须在发出请求前拒绝整批。
- **V1.2.0 真实 Anki 待验收：** 检查 Advanced Batch Size 可编辑下拉框（预设 1–10、默认 1、可输入 1–99，最多两位，可保存），灰色 Resolve 按钮已移除且失效字段仍可取消勾选，Easy OCR 显示及行为不变；B=1 原单 JSON、B=10 JSONL 的 10→2→下一批 10、重复/未知 ID、截断与损坏行、连续三次零进展终止、明确上下文超限弹窗，以及非取消部分成功安全提交。
- 在 Windows/Linux 等上位 SPEC 要求的平台，用真实 Anki 检查多次请求最后只有一个 Undo、写入前快照冲突、提交前 Cancel 不写入、提交排队/运行中 Cancel 及关闭 TextTab 后后台协调对象正确结算。自动化 Mock 测试不能替代这些实机验收。
- 核查 `.github/workflows/advanced-batch-tests.yml` 在候选 Commit 的四平台 CI；失败或未运行不得记为通过。
- 测试提示词 New、Save、Save As、Delete、Import、Export。确认已删除的 Online 提示词按钮不再显示，Default 保护仍有效。
- 至少对一个远程 Provider 使用 Check；确认关闭并重新打开后模型选择保持不变。
- 确认 13 个 Provider 的 Reasoning 均可选择。Model Default 不向请求加入推理覆盖字段；对自定义 OpenAI-compatible NInfer，验证 Off 发送 `reasoning_effort: "none"`，并通过服务器日志判断实际行为。不能将不支持该字段的官方平台视为已经生效。
- 确认界面显示完整 **Temperature**。打开 DEBUG 时，终端记录最终发出的 Temperature、Reasoning、输出 Token 上限和 Stream，且不泄露 API Key、Prompt 或完整响应。
- 检查底部左侧 GitHub → Restore Default LLM Parameters → Help，以及右侧 Close → Generate。Restore 仅恢复当前 Text Provider，保留 API Key 和本地服务器地址，在 Audio 标签隐藏。
- **Mac mini 实机**检查 Audio 所有 Speed/Volume 滑杆两端的 Qt 左右箭头可见；每次点击调整 1%，边界及不支持的控件保持正确禁用。
- 使用 Edge TTS 和可用的本地 Kokoro 测试 Audio Profile、Voice、生成及 `[sound:...]` 字段写入，确认切换 Profile 不错误保存草稿。Edge 音色列表显示地区代码加人名（如 `US-AriaNeural`、`GB-SoniaNeural`）；Voice ID 与筛选逻辑不变。
- **V1.1.1 Library：** 导出统一 JSON，检查包含已保存的 Easy/Advanced Prompt 和 Edge/Kokoro 四 Voice 的 Audio Profile，且不含 Provider API Key、本地 Profile UUID。使用临时 Anki 配置导入，检查冲突重命名、重复导入幂等性及原有 UUID、选中 Profile 不变。
- **V1.1.1 GitHub：** 使用临时测试仓库和最小权限 Fine-grained Token，检查包含子目录路径的 Save/Load、公开与私有仓库的权限表现、切换仓库的 Token 状态、Replace/Remove 确认及非覆盖合并。公开仓库可被他人读取，测试不得上传私人 Prompt。
- **V1.1.1 Audio 与批量预检：** 检查四个 Voice 区块、已有三槽 Profile 的迁移，以及 Edge/Kokoro 生成；Text Easy 和 Audio 遇到混合 Note Type 时必须在请求或写入前拒绝整批，同一 Note Type 不同 Card Template 可一起处理。
- 按 `docs/testing/library-github-sync-v1-acceptance.md` 在支持的桌面系统执行真实 Anki/Qt 和凭据库验收。GitHub Actions 使用 Mock 代替系统凭据服务，不能视为真实平台测试完成。
- 确认 `.github/workflows/library-sync-tests.yml` 对待发布 Commit 的四平台矩阵全部通过；排队或失败不得记录为通过。
- **当前源码版本已升为 1.2.0：** `manifest.json` 是唯一权威版本号，`ainotepro/version.py` 负责读取，窗口标题显示 `AINotePro — v1.2.0`；`__init__.py` 不重复硬编码数值。此处仅表示源码版本与合并，不等于已发布 AnkiWeb。发布前仍须完成用户负责的真实 Anki/Qt 与 Undo 验收、备份 `user_files` 并单独确认打包发布。此前单 Prompt 导出 JSON 不能直接作为新版统一 Library 导入。
- 视本次发布的功能声明，测试真实视觉模型的 OCR。
- 确认 `user_files/user_config.json` 及提示词跨版本升级仍保留，失败请求不将 `[Error]` 写入字段。
- 确认 OCR 拒绝 Anki 媒体目录外的 `file://` 文件，以及远程 `http(s)://` 图像 URL。

## 2. 文档检查

- 同步 `README.md` 和 `README.zh-CN.md`。
- 同步 `changelog.md` 和 `changelog.zh-CN.md`。
- 同步 `docs/ANKIWEB_DESCRIPTION.md` 和 `docs/ANKIWEB_DESCRIPTION.zh-CN.md`。
- 行为变更时同步本检查表和 PRIVACY 的中英文版本。
- 检查 GitHub Issues 链接及外部说明是否有效；确认隐私文字与实际传输一致。
- 核对 `LICENSE`、`THIRD_PARTY_NOTICES.md` 和 `libs/` 中第三方依赖的许可信息。

## 3. 打包前清理

包中不得包含：

- `__pycache__/`、`*.pyc`、`*.pyo`
- `user_data/`
- `user_files/user_config.json`、`user_files/gen_text/`
- `ainotepro/logs/`
- `.git/`、`.DS_Store`、`*.bak`、`meta.json`

`meta.json` 是 Anki 安装插件后生成的元数据，不是发布源文件。

## 4. 源码版本与插件分发分支

正式源码发布以 **main** 为准，`v1.2.0` Git Tag 应指向 main 的发布 Commit。
main 保留完整代码、`docs/`、`tests/`、`.github/` 与开发文档。

**addon/v1.2.0** 只包含可安装插件运行所需内容：`__init__.py`、
`manifest.json`、`ainotepro/`、`libs/`、`user_files/README.txt`、
许可证与隐私说明；不包含 `docs/`、`tests/`、`scripts/`、`.github/`、
生成日志、缓存或备份。

在 Mac 本地仓库中，无须切换到 addon 分支就可构建安装包：

~~~bash
git fetch origin --prune --tags
git archive --format=zip --output=AINotePro-v1.2.0.ankiaddon origin/addon/v1.2.0
unzip -t AINotePro-v1.2.0.ankiaddon
unzip -p AINotePro-v1.2.0.ankiaddon manifest.json
shasum -a 256 AINotePro-v1.2.0.ankiaddon
~~~

安装包根目录必须直接是 Anki 插件入口文件，不能额外包含 `AINotePro/`
外层目录。不要直接将 main 打包为可安装插件，否则会包含测试和开发文件。
GitHub Release 和 Git Tag 对应 **main 的源码版本**，其 `.ankiaddon`
附件来自 **addon/v1.2.0**。更新已发布的 Tag 或附件前，应核对对应版本及校验值。
发布 GitHub 源码版本并不等于同步上传 AnkiWeb。

## 5. 上传 AnkiWeb

1. 打开 https://ankiweb.net/shared/addons/ ，按页面流程上传 `.ankiaddon`。
2. 标题使用 `AINotePro - AI-powered note enhancement for Anki`。
3. 支持地址使用 GitHub Issues；说明来自英文 `docs/ANKIWEB_DESCRIPTION.md`（需要中文介绍时使用中文同名文件）。
4. 受测 Anki 版本应填写实际完成验证的版本，不得以静态检查代替实测。

## 6. 上传后

- 在全新 Anki Profile 中安装插件，检查启动、Browse、编辑器、Text、提示词、Audio 及写入。
- 将正式 AnkiWeb 插件代码更新到 README。
- 确认发布版本后再创建仓库 Tag。
