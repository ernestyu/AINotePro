# AINotePro 发布检查表

[English](RELEASE_CHECKLIST.md) | [简体中文](RELEASE_CHECKLIST.zh-CN.md)

本检查表用于发布新的 `.ankiaddon` 到 AnkiWeb 前的验证。以下为**待执行项目**，不是本次文档更新已完成的测试报告。

## 1. 发布前功能检查

- 启用插件并启动 Anki，确认没有启动异常。
- 从 Browse 菜单及笔记编辑器工具栏打开 AINotePro。
- 选择一条笔记生成 Text，确认输出写入目标字段；再验证选择多条笔记时的生成与写入。
- 在 Advanced 中验证来源/目标字段与 `{OUT:字段名}` 声明、严格 JSON 格式以及整批预检。选中**超过 100 条有效笔记**时，不应再因固定条数限制拒绝；不合格笔记仍须在发出请求前拒绝整批。
- 测试提示词 New、Save、Save As、Delete、Import、Export。确认已删除的 Online 提示词按钮不再显示，Default 保护仍有效。
- 至少对一个远程 Provider 使用 Check；确认关闭并重新打开后模型选择保持不变。
- 确认 13 个 Provider 的 Reasoning 均可选择。Model Default 不向请求加入推理覆盖字段；对自定义 OpenAI-compatible NInfer，验证 Off 发送 `reasoning_effort: "none"`，并通过服务器日志判断实际行为。不能将不支持该字段的官方平台视为已经生效。
- 确认界面显示完整 **Temperature**。打开 DEBUG 时，终端记录最终发出的 Temperature、Reasoning、输出 Token 上限和 Stream，且不泄露 API Key、Prompt 或完整响应。
- 检查底部左侧 GitHub → Restore Default LLM Parameters → Help，以及右侧 Close → Generate。Restore 仅恢复当前 Text Provider，保留 API Key 和本地服务器地址，在 Audio 标签隐藏。
- **Mac mini 实机**检查 Audio 所有 Speed/Volume 滑杆两端的 Qt 左右箭头可见；每次点击调整 1%，边界及不支持的控件保持正确禁用。
- 使用 Edge TTS 和可用的本地 Kokoro 测试 Audio Profile、Voice、生成及 `[sound:...]` 字段写入，确认切换 Profile 不错误保存草稿。Edge 音色列表显示地区代码加人名（如 `US-AriaNeural`、`GB-SoniaNeural`）；Voice ID 与筛选逻辑不变。
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

## 4. 构建 .ankiaddon

在仓库根目录执行：

```bash
find . -name "__pycache__" -type d -prune -exec rm -rf {} +
rm -f ../AINotePro.ankiaddon
zip -r ../AINotePro.ankiaddon * \
  -x "user_data/*" "user_files/*" "ainotepro/logs/*" "*.pyc" "*.pyo" ".git/*" "*.DS_Store" "*.bak" "meta.json"
zip -ur ../AINotePro.ankiaddon user_files/README.txt
zipinfo -1 ../AINotePro.ankiaddon | head
```

压缩包顶层应直接包含 `__init__.py`、`ainotepro/`、`libs/`、`manifest.json`、`README.md`、`user_files/README.txt` 等，不能再嵌套一层 `AINotePro/`。

## 5. 上传 AnkiWeb

1. 打开 https://ankiweb.net/shared/addons/ ，按页面流程上传 `.ankiaddon`。
2. 标题使用 `AINotePro - AI-powered note enhancement for Anki`。
3. 支持地址使用 GitHub Issues；说明来自英文 `docs/ANKIWEB_DESCRIPTION.md`（需要中文介绍时使用中文同名文件）。
4. 受测 Anki 版本应填写实际完成验证的版本，不得以静态检查代替实测。

## 6. 上传后

- 在全新 Anki Profile 中安装插件，检查启动、Browse、编辑器、Text、提示词、Audio 及写入。
- 将正式 AnkiWeb 插件代码更新到 README。
- 确认发布版本后再创建仓库 Tag。
