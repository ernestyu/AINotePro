# AINotePro — Text Provider UI 精简与 LLM 终端诊断 SPEC

2026-11-03 · DRAFT，待审核 · 只新增本 SPEC，尚未授权开发

固定代码基线：`6922a65cb38b9a2cebe9f3cb05971a98319a2d8c`
开发分支：`feat/text-provider-ui-simplify-20261103`

## 0. 目标与边界

本轮是**删除不需要的功能并改善现有操作**，不是 Provider V3 重构。只保留当前 13 个 Cloud/Local 内置 Provider、它们可编辑的 Chat Endpoint 或 Server Address、Model/Refresh/Check、Temperature、适用的 Reasoning，以及 Easy/Advanced/OCR/Audio 既有能力。

**删除的功能连同其专属配置与调用代码一起删除；保留的功能连同其实际请求能力一起保留。** 不创建迁移表、兼容壳、新配置版本、通用协议层、CAS、任务框架或日志服务。不扩大修改范围。

## 1. 移除 Legacy / Other

- 从 Provider 下拉列表、预设来源、Provider Factory 注册和相关测试中**移除四个 Legacy 专属条目**：Together (`together`)、Perplexity (`perplexity`)、LM Studio (`lmstudio`)、LocalAI (`localai`)。不保留“Legacy / Other”分组或可选项。
- 在已存在的插件配置 `user_files/user_config.json` 中清除 `text.together`、`text.perplexity`、`text.lmstudio`、`text.localai` 四个对象；新的默认配置也不生成它们。这里清理的是本次刚加入的 Legacy Provider 设置，不涉及 Anki 笔记、媒体、Audio Profile 和 Prompt。
- 若 `text.provider` 指向被删除的 Legacy key，置为有效的 `openai` 默认选择；不要让 UI 落入无法使用的选项。其他保留 Provider 的配置不得变化。
- 使用现有 ConfigManager 的读/写机制完成一次简短、确定的字段清理即可；不额外备份、不建立历史迁移流程。不得删除 `user_files` 目录，也不删除其他非目标字段。

## 2. 移除 Custom 与专属 Models Endpoint UI

- 完整删除 New Custom、Save Custom、Rename、Delete、Cancel、Custom 下拉分组、`custom:<id>` 分发、草稿状态、切换/关闭确认及管理函数；删除配置中的 `text.custom_providers`，不保留 Custom 数据或 Custom 兼容路径。若当前 `text.provider` 为 `custom:<id>`，改选 `openai`。
- 删除**此次为 Custom 加入的 Models Endpoint 输入框**及其 UI 编辑、保存、状态跟踪和显示逻辑。
- **不得删除保留的 13 个 Cloud/Local Provider 的模型查询能力**：保留 `provider_presets.py` 中对应的模型列表接口定义，保留现有 `list_models`、Refresh 和 Ollama 原生 `/api/tags`。不因为删 UI 而删掉内置 `models_endpoint` 配置或请求实现。
- 对保留 Provider，Refresh 按当前实际配置中的内置 Models Endpoint 请求；旧的仅 `base_url` 配置仍按既有路径推导（不因删 UI 恢复官方 URL）；没有可用模型列表接口的预设允许手动输入 Model 并给出明确提示。用户既有 `chat_endpoint` / `models_endpoint` 数据不因本轮删除 UI 自动清除。
- 保留 Cloud Chat Endpoint 的编辑和保存能力；保留 llama.cpp、vLLM、Ollama 的服务器配置和对应请求协议。保留 Model 手工输入。**不新增**用于代替 Custom 的配置形式。

## 3. 底部按钮与 Restore Default LLM

- 主对话框底部操作按钮按 **Help → Restore Default LLM → Close → Generate** 排列；不在 Text 页内部保留旧 `Restore official URLs` 按钮。
- `Restore Default LLM` 只在 Text 页可用，Audio 页隐藏或禁用。按钮只针对**当前选中的一个**保留 Provider。
- 对当前云端 Provider：恢复官方 Chat Endpoint、默认 Model、Temperature=0.7 和当前 Provider 的 Reasoning 选择为 Model Default（清理该 Provider 的按模型 Reasoning 覆盖）。若当前 Provider 的 Models Endpoint 曾被用户修改，随该 Provider 一起恢复其已定义的官方 Models Endpoint；不触碰其他 Provider。
- 对当前本地 Provider：恢复默认 Model（如预设有）、Temperature=0.7、Reasoning 为 Model Default；**保留用户自定义的 Server Address**（包括本地 Chat Endpoint 指向的远程机器地址）；Models 查询地址须继续对应当前本地服务器，不能悄悄跳回 `127.0.0.1`。
- 所有平台的 **API Key 原样保留**。不重置其他 Provider、Prompt、Audio、Source/Destination、笔记和媒体。点击恢复后应立即更新当前 UI 和配置；如果保存失败，报告错误并保留可恢复的 UI 状态，不显示虚假成功。
- 名称 `Default LLM` 在此仅指当前内置 Provider 的以上默认参数，**不是**“恢复全部插件设置”。

## 4. 在原有请求路径增加终端诊断

- 沿用现有 `debug_logging` / `AINOTEPRO_DEBUG=1` 开关，**不添加网络探测、远程日志服务或新请求**。普通模式保留必要的一行开始/结束/失败摘要；DEBUG 模式显示细化时间与调用步骤。
- 对每次 Text 的 Check、Easy、Advanced（以及调用同一个 Provider 的图像请求）记录：Provider、Model、请求方法与目标 URL（不含敏感 query 参数）、请求开始时间、HTTP 状态或失败类型、HTTP 请求总耗时、响应 JSON/内容处理耗时、返回文本长度；API 响应确实包含 `usage` 时记录输入/输出 Token 数；批次记录进度、完成/失败/取消数量及总耗时。
- 在调用前、HTTP 返回后、解析结束后分别打时间点，以区分卡在发请求、等待服务端还是处理结果；请求失败也应记录耗时。可以通过简单的 `time.perf_counter()` 和已有 `print()` 完成。仅在服务端返回可用细分计时字段时输出该字段；非流式请求的总耗时**不能**标注为精确的 Prefill/Decode。
- 不打印 API Key、Authorization 头、完整 Prompt、笔记全文、响应全文；URL 若包含密钥 query 参数应隐藏相应值。日志不得修改请求 Body、超时、重试次数、网络调用次数或生成结果。
- Ollama 和 OpenAI-compatible 两条已有实现路径都要覆盖；检查 Batch 进度与错误统计可用，不在 UI 主线程做昂贵的调试处理。

## 5. 非目标行为与交付

- 保持 13 个 Cloud/Local 内置预设、Anthropic/Gemini 的 OpenAI-compatible 请求、Ollama Native API、旧 `base_url` 与新 `chat_endpoint` 的既有优先级；保留用户已配置的 URL、Key、Model。
- 不改 Easy/Advanced 的输出协议、预检、JSON 校验、Undo、OCR 同步路径；不改 Audio 的三 Voice、Speed/Volume、Preview、Pitch=0 及历史浮点值。清理删除功能时排除其无关文件。
- 测试只做普通 Python 语法、必要单元、Mock HTTP、隔离配置清理与 UI Stub；**禁止 Anki 沙箱、启动 Anki、触碰真实 Anki Profile/笔记/媒体**。用户自行完成真实 Anki 测试。
- 开发前检查引用，完成后按**全局代码与真实调用链**自审：Provider 选择/切换/保存、删除功能后首次打开、Refresh/Check、Easy/Advanced/OCR、Audio、底部按钮、调试日志。按共同根因集中修补；不为无关边界情况增加架构。
- 本 SPEC 提交本身只改文档，不修改生产代码。开发须另行授权，交付列出 Commit、实际测试命令、PASS/FAIL/SKIP，以及用户需要实机验证的项目。

## 6. 最少验收场景

1. 新安装仅显示 Cloud/Local 13 项；旧安装带 Legacy/Custom 时清理目标键并恢复有效选择，其他设置不变。
2. 选 DeepSeek 编辑自定义 Chat URL、Key、Model 后保存、切换、重开；仍使用自定义 URL。Refresh 仍用该 Provider 对应的模型列表接口；不依赖被删除的 UI 输入框。
3. 选 Ollama 或远端 llama.cpp/vLLM：可连接自定义服务器并刷新模型；恢复默认 LLM 不改变该服务器地址。
4. Cloud 的 Restore 只恢复当前平台默认值、保留 API Key；切换回其他平台，设置没有变化。
5. Audio 页看不到可用的 Restore Default LLM；Generate、Close、Help 保持原行为。
6. 用终端启动插件，DEBUG 模式可看到一条 LLM 请求从开始到返回/失败的耗时、状态与可用 usage；没有额外 HTTP 请求或密钥泄露。
7. Easy/Advanced、OCR、Audio 的原有入口和行为未受删除代码影响。
