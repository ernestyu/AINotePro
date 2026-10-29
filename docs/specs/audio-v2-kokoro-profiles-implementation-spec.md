# AINotePro Audio V2 — Kokoro 集成与 Profile 改进实施 SPEC

- 状态：**PROPOSED / 待独立审计，禁止据此直接发布**
- 日期：2026-10-29
- 仓库：`ernestyu/AINotePro`
- 代码基线：`main@2f3efa526b5e16f0d8b0eb5443d42f38c91e7e3c`（v1.0.0）
- 外部依赖基线：`ernestyu/kokoro-tts@d3f8333765d4e3432e51a5ead831b80096064a4e`
- 目标 Anki：现有 README 声明的 Anki 26.05+；以真实安装版本复测为准
- 本文为设计规范，**不是已实现功能清单**。实现前需独立架构/覆盖审计。

## 1. 背景与已验证事实

AINotePro 当前 Audio 标签使用 Edge TTS；提供三个可勾选的 Voice 区块、每个区块的音色、性别、语速、音量、音调与 Preview，支持从源字段生成 MP3 并在目标字段写入 Anki `[sound:...]`。当前实现位置：`ainotepro/ui/tts_tab.py`、`ainotepro/services/audio/edge_tts.py`、`ainotepro/services/provider_factory.py`、`ainotepro/core/utils.py`、`ainotepro/config/manager.py`。

用户明确要求：**勾选多个 Voice 时，每张笔记随机选择其中一个音色**，以减少长时间听同一种音色的疲劳。当前 GitHub `main` 中 `on_generate_tts()` 的循环遇到第一个启用区块即 `break`，不能从代码证明随机选择；用户实际安装版本的体验可能不同。开发前必须核对本地运行版本；V2 验收以随机选择语义为准，不删除三个 Voice 区块。

Kokoro 运行在同一台 Mac mini 的独立 Python `.venv` 中；Gradio 服务监听 `http://127.0.0.1:7860`，命名端点 `/synthesize`。2026-10-29 已实测 `gradio_client.Client.predict(text=..., voice="af_heart", speed=0.95, api_name="/synthesize")` 返回两个 MP3 路径与状态，客户端取得真实文件（65,324 bytes）。**这验证的是 Python Gradio 客户端链路，不代表任意原始 HTTP 协议已验证。** 当前服务接受英文音色 `af_*`、`am_*`、`bf_*`、`bm_*`；语速 0.7–1.3；文本最多 6000 字符；服务端自行保留输出文件。Kokoro 不需要 API Key。

## 2. 目标、边界与不变项

1. 保留 Text 标签、原有 Edge TTS、Anki 媒体写入与手机端通过 Anki 同步播放的机制；不要求手机连接 Kokoro。
2. Audio 标签新增可选的 `kokoro_gradio` Provider；保留三个 Voice 区块，按当前 Provider 切换音色列表与适用控件。
3. 支持完整 Audio Profile 的命名、保存、另存、加载、删除、重新打开后恢复；Provider、服务 URL、三个 Voice、随机策略、字段选择均受 Profile 管理。
4. 生成和网络 I/O 不阻塞 Anki Qt 主线程；进度、取消、失败隔离与 Anki collection 写入安全。
5. 避免重复追加 `[sound:...]`，不破坏既有字段内容或用户原有音频；Preview 不污染 Anki 媒体库。
6. Kokoro 不在线时不强行选择成功；保留已保存 Profile，提供可重试的连接探测。
7. 不改动 `kokoro-tts` 服务端，不部署 FastAPI，不复制模型/虚拟环境到 Anki，不引入移动端运行时依赖，不进行大规模 Text/架构重构。

## 3. Provider 契约与 Kokoro 接入

### 3.1 统一契约

维持 `AudioProvider.generate(text: str, config: dict) -> bytes` 的输出约定；返回完整、非空 MP3 bytes，失败时抛出可区分的异常，不返回假成功。将 `kokoro_gradio` 注册到 `create_provider("audio", ...)`；Edge TTS 继续使用现有实现。可增加可选的 `probe()`、`list_voices()` 能力，不能要求所有旧 Provider 重写。

Kokoro 配置：`base_url` 默认 `http://127.0.0.1:7860`，`api_name` 固定 `/synthesize`（除非有明确迁移理由），`voice` 为实际服务返回的有效音色，`speed` 为浮点倍速。客户端读取 Gradio 返回的**客户端可访问** MP3 文件路径/下载结果并立即复制成 bytes；绝不将 Gradio 临时路径写入 Anki 字段或长期配置。验证文件存在、非空、可识别为 MP3；清理插件自己创建的临时文件，不擅自删除 Gradio 服务端的文件。

### 3.2 依赖与传输决策门槛

Anki Python 与 Kokoro `.venv` 相互隔离。开发须先在 **Anki 实际内嵌 Python 环境** 验证 Gradio 客户端依赖能否兼容、可否安全打包；同时可研究标准库/现有轻量依赖实现 Gradio 调用，但必须有真实端到端协议验证，**不能臆测 `/synthesize` 是直接返回 MP3 的普通 POST**。优先选择可测试、可打包、跨 macOS/Windows/Linux 不冲突的最小方案；审计应要求在实现 SPEC 中记录选择、依赖清单、许可证、失败/超时/队列行为及替代方案。禁止在 Anki 启动时隐式 pip 安装依赖。

### 3.3 服务探测

用户选择 Kokoro、加载 Kokoro Profile 或点击 Retry 时，在后台执行有限超时探测：确认 URL 可访问、服务是预期 Gradio API、存在 `/synthesize` 且参数兼容（`text`、`voice`、`speed`）、获取可用音色列表；不触发模型合成。不能仅凭 7860 端口开放就判定成功。探测期间禁用 Kokoro Generate；成功后才使该 Provider 可用于生成；失败显示原因与 Retry，保持先前有效 Provider/未保存界面状态，不能静默回退为 Edge TTS 后继续写音频。加载离线 Kokoro Profile 时允许显示其保存的参数，但标记离线并禁用生成，不能删除 Profile。生成前/过程中仍要处理服务下线、排队超时、无效音色。

首版默认仅允许本机 loopback `127.0.0.1`/`localhost`，不自动暴露 LAN；如果允许编辑 URL，必须限制危险 scheme、非本机目标和重定向，并明确后续远程扩展另立需求。日志不记录全文敏感笔记文本。

## 4. 三 Voice 区块与随机选择（核心业务要求）

三个 Voice 区块结构保留。每个区块独立：`enabled`、`voice`、`gender`、`speed`，Edge TTS 另有 `volume`、`pitch`；Preview 文本可单独保存。Kokoro 仅显示/启用受 API 支持的参数：语言固定 English，音色按服务返回列表筛选，性别可由音色前缀筛选（`af/am/bf/bm`）；语速 UI 映射到 0.70–1.30 的浮点倍数；Volume/Pitch 隐藏或禁用但不能篡改已保存的 Edge 参数。Edge TTS 继续保留其语言、音色、音量、音调能力；移除无意义的 Audio API Key 输入或在两种 Provider 下隐藏。

每张有效笔记先收集全部 `enabled=True` 且在当前 Provider 下有效的区块，再对其做**均匀随机选择**（每个启用区块等概率；同名音色的两个区块仍视为两个可选配置），所选区块的全部参数必须成套使用。随机选择单位为**笔记**而非整批；Preview 只使用被预览区块，不随机。没有启用任何有效 Voice 时必须阻止生成并给出明确提示。可在后续增加“避免相邻两张使用相同音色”的可选策略，但不得悄悄改变本版均匀随机规则。支持可注入随机数源以测试单选、多选、分布、参数配对与重试一致性。

## 5. Audio Profile：完整保存与恢复

### 5.1 数据与兼容性

在既有 `user_files/user_config.json` 的 `audio` 下新增版本化 `profiles` 结构与 `last_profile_id`，使用稳定 ID 与可编辑显示名；Profile 至少包含：`schema_version`、`name`、`provider`、Provider 专属设置（Kokoro URL；Edge 语言等）、三个 Voice 的启用/音色/性别/语速/音量/音调/Preview 文本、随机策略、源字段名与目标字段名。仅存必要字段，不存 API Key、临时音频路径、模型权重。保留未知旧配置键与 Text 配置，不破坏已有 Prompt/Profile 机制。

旧版本 `audio.edge_tts` 配置须以**幂等、无损**方式迁移为一个默认 Edge Profile；原配置缺少三 Voice 状态时只填有据可依的默认值，不假称能恢复从未保存过的 UI 状态。重复启动、重复迁移不能生成多个同名默认 Profile。已有 `ConfigManager._deep_merge_dicts` 与 `save_all()` 的默认合并逻辑必须专门审查：删除 Profile 后不得被默认值合并回来。保存采用临时文件+原子替换并妥善处理损坏 JSON；配置变更失败不应丢失原文件。

### 5.2 UI 语义

在 Audio 标签顶部提供 Profile 下拉列表及 **Load / Save / Save As / Delete**。首次打开默认恢复上次成功加载的 Profile；用户在下拉框选择其他 Profile **不立即覆盖未保存编辑**，点击 Load 才应用。Save 覆盖当前 Profile；Save As 输入新名称创建新 Profile；Delete 二次确认且不能使配置进入无可用 Profile 的非法状态。未保存编辑时切换、关闭、Load 或 Delete 必须给出保存/放弃/取消的清晰选择；仅点击 Generate 不应隐式保存 Profile。

Profile 可保存源/目标字段名称，但不同笔记类型字段可能不一致：加载时校验，字段缺失则显示需重新选择并禁止写入，不能悄悄改成下拉框第一个字段。Provider 离线不影响 Profile 的加载、编辑、保存或删除，只影响生成。UI 中要清楚区分“当前编辑配置”“已保存 Profile”“服务连接状态”。

## 6. 后台任务、Anki 线程边界与失败处理

网络探测、TTS 请求、MP3 下载与校验在后台执行；Qt 控件、进度更新、Anki `mw.col` 读取/写入、媒体库 `write_data` 等操作遵循 Anki 26.05 线程与 collection 约束，不从任意工作线程直接修改笔记。建议采用 Anki 提供的任务管理机制或经验证的 Qt worker+主线程交接，必须防止对话框关闭后回调访问已销毁控件。不要在主线程等待 worker `join`/同步 `future.result()`。

在主线程先获取当前待处理笔记的必要快照（ID、文本、字段、生成策略），后台按每张笔记合成，结果回主线程写媒体与笔记；避免一次性把大量笔记内容无界缓存。初版顺序处理、并发度 1，与 Kokoro Gradio 队列一致。用户点击 Cancel 后不再启动下一张，正在运行的一张可安全完成或超时；UI 可响应。每张笔记单独报告成功/跳过/失败；中途失败不回滚其他已成功笔记，且不能出现只有字段标签没有对应媒体的半完成状态。对关闭窗口、失去连接、重复点击 Generate、选中笔记变化、源/目标字段变化有明确行为。遵守 Anki 推荐的可撤销 collection 操作，不能破坏既有撤销历史。

## 7. 字段与媒体安全：幂等、替换、预览

生成前校验源字段、目标字段及其所属笔记类型；源字段可能含 HTML、`[sound:...]`、换行或富文本，须提取可朗读纯文本且不把既有声音标记读出来，保留正常标点与英文缩写。空文本跳过；Kokoro 超过 6000 字符时明确报错或经用户确认后拆分，不能静默截断。

**默认策略：目标字段已有声音引用时跳过，不追加重复音频。** 可提供显式 Replace 选项，但只允许删除/替换能被可靠识别为 AINotePro 管理的目标音频；对于历史未知来源的 `[sound:...]` 必须保守保留并提示用户手工处理，不能凭文件名近似匹配或简单正则删除所有声音标签。无声音时保留目标字段既有文字/HTML 并添加一个有效引用；对重试、重复 Generate、部分失败、同源/目标字段应有幂等保护和风险确认。需要明确“管理来源”的记录方案、配置丢失后的降级行为、Anki media 重命名后的映射更新；不得将临时缓存路径作为引用。不要为了清理字段而自动删除 Anki 媒体文件（可能被其他笔记引用）。

Preview 直接使用临时 MP3 播放，不调用 `add_audio_to_media_collection`；预览结束/关闭后安全清理插件临时文件，兼顾播放器尚在读取的情况。正式生成使用 Anki 媒体 API 写入 bytes，获得真实文件名，再写 `[sound:文件名]`；移动端仅需 Anki 媒体同步，无需 Kokoro。

## 8. 代码改动边界与建议文件

- 新增 `ainotepro/services/audio/kokoro_gradio.py`（命名可调整）：服务探测、音色发现、合成与 MP3 bytes 返回。
- 修改 `ainotepro/services/provider_factory.py`：注册 Provider。
- 修改 `ainotepro/ui/tts_tab.py`：Provider 切换、三 Voice 随机、Profiles、连接状态、后台任务 UI、字段写入策略。
- 修改 `ainotepro/config/manager.py` / `defaults.py`：版本化 Audio Profile、无损迁移与持久化；避免重复默认配置源不一致。
- 按需要抽出可单测的 `audio` 业务逻辑/任务编排模块；复用 `ainotepro/core/utils.py` 的媒体 API，必要时补充安全操作。
- 更新 `README.md`、`docs/RELEASE_CHECKLIST.md`、`docs/ANKIWEB_DESCRIPTION.md`、`changelog.md`，及新增测试。
- 不修改 Kokoro 服务端，不改 Text 功能接口，不引入未经验证的重型依赖。

## 9. 必须通过的测试与验收

**静态/单元**：Provider 工厂选择 Edge/Kokoro；探测成功/拒绝错误服务/离线/超时；无效音色/无效语速/空 MP3；三 Voice 随机选择（单个、多选、禁用、参数不串用、固定种子）、两 Provider 控件映射；Profile 新建/保存/加载/另存/删除/重名/缺失字段/损坏配置/迁移幂等；配置删除不复活；HTML 转文本；字段含其他声音与 HTML 时不丢内容；重复生成不重复追加；Preview 不调用 Anki 媒体写入；取消与失败隔离。网络调用与 Anki collection 必须 mock，测试不依赖在线 Kokoro。

**实际 Anki 集成（Mac mini）**：Anki 26.05+ 启动无 traceback；Edge TTS 原有功能回归；Kokoro 离线不可生成但可加载 Profile，启动后 Retry 可用；音色列表与实际服务匹配；三个 Voice 每笔记随机生效；单张、10 张、100 张笔记；生成时窗口可操作且可取消；失败/重试/关闭对话框；同字段与不同字段；字段已有普通文字/HTML/音频；Preview 不新增媒体；保存 Profile、退出 Anki、重启、加载完全恢复；升级插件后 `user_files` 不丢；音频同步到手机可播放。

**验收门槛**：无新增永久后台服务；没有额外 Kokoro 模型加载；不阻塞 Qt 主线程；无静默 Provider 回退；无重复追加或误删用户声音；没有将敏感笔记发往非选定 Provider；打包后的依赖在 Anki 内可导入；完整测试证据与限制记录后才可发布。

## 10. 待独立审计重点（设计决策，不得默认为已解决）

A. Gradio 客户端 vs 轻量 HTTP 的协议可靠性、依赖体积、Anki 内嵌 Python/Qt 兼容性与许可。
B. Profile 存储与迁移是否能兼容旧 `ConfigManager` 的深度合并行为；是否需要独立 Profile 文件以避免删不掉。
C. Anki collection 线程、撤销、媒体写入、关闭窗口与取消的安全边界。
D. 音频归属/替换策略能否可靠识别“插件生成”而不误伤其他声音；跨设备同步后 provenance 的语义。
E. 实际本地插件版本与 GitHub `main` 在随机音色上的差异；如何复现并回归。
F. 服务探测与 Profile 加载的 UI 状态机，尤其“离线但可加载”“切换失败不误用 Edge”。
G. 当前 Audio 默认 Language 显示 Afrikaans、API Key 对 Edge/Kokoro 无意义、三 Voice 当前只取首项等现有行为与兼容迁移。
H. 现有 `AIManager.generate_audio_for_field()` 与 `TTSTab.on_generate_tts()` 是两条音频路径，需审计是否共用统一策略，避免修好 UI 后另一入口仍可重复追加。

## 11. 音色可理解性、官方评级与多语言能力（2026-10-29 补充）

本节为**规范性补充**，覆盖前述章节中“英语固定”“只显示 voice ID”相关的 UI 表述；不改变“Audio V2 不修改 Kokoro 服务端”的实施边界。官方 54 音色完整表、来源与评级见 [官方音色语言对照](../reference/kokoro-official-voice-language-catalog.md)。

### 11.1 友好音色选择器

- 三个 Voice 区块保留，各区块以 `语言/口音 → 性别 → 音色` 分层筛选；例如 `American English → Female → Heart (af_heart) · 官方 A`，`British English → Female → Emma (bf_emma) · 官方 B-`。选择器可复用同一组件，三个区块状态独立。
- 美式英语、英式英语应明确区分，不应只显示抽象前缀 `af/am/bf/bm`；性别由官方 f/m 标记推导。保留原始 ID 供技术排查和 Profile 序列化，用户可见名称为易读标签。
- 采用模型作者 `hexgrad/Kokoro-82M/VOICES.md` 的 `Overall Grade` 作为可选展示和排序元数据；未评级显示“未评级”，**不得编造年龄、语气、风格或声线性格**。评级是官方训练数据综合估计，不是普适的听感评分。默认可优先排列高评级音色，但低评级仍可选。
- 当前实际可用音色必须通过运行时 Gradio API schema / `list_voices()` 探测；官方 54 音色清单仅为展示元数据，不能当作本地可用能力。UI 对离线/不可用 Profile 音色标记警告，不静默替换。
- 选择不同国家/口音时，仍以所选语言文本与对应 voice 匹配为前提；不能将跨语言声音当作同一语言的口音变体。

### 11.2 多语言范围与真实能力

Kokoro v1.0 官方覆盖**8 种语言、9 个语言/口音组、54 个音色**：美式英语、英式英语、日语、普通话、西班牙语、法语、印地语、意大利语、巴西葡萄牙语。英语相对成熟，其他语言官方指出 G2P/训练数据限制；不能以音色数量推断质量。日语/普通话需要 `kokoro-mlx[ja]` / `kokoro-mlx[zh]` 可选依赖。

**现有 Mac mini 的 `ernestyu/kokoro-tts/scripts/webui.py` 只发现并接受 `af_/am_/bf_/bm_`，即 28 个英语音色；非英语未通过该服务端的端到端验证。** 本次 Audio V2 第一阶段只要求这 28 个英语音色的友好分组/性别/评级、随机抽取与 Profile 恢复，且不改 Kokoro 服务端。Profile 数据结构必须预留通用 `language`/`locale` 字段，不把英语前缀硬编码为长期唯一模式。

若要把非英语纳入可交付范围，必须作为**明确批准的第二阶段**：修改 `kokoro-tts` 服务端音色发现和验证、验证各语言 G2P 依赖和输出、调整语言/音色 API 能力探测、按语言增加实际合成与 Anki 媒体测试。不得仅因为官方模型支持多语言，就在插件中展示无法合成的选项或宣布功能完成。

### 11.3 追加验收

- 28 个现有英语音色按 American/British、Female/Male 正确分组，ID、显示名、官方评级匹配官方目录；未知评级显示“未评级”。
- 动态探测仅允许当前 API 返回的音色；服务音色变化后能保留失效 Profile 原值并提示，不自动改写。
- 三 Voice 区块可独立选择不同口音与性别，并按笔记均匀随机选择完整参数组。
- 语言、口音、性别、voice ID 均随 Profile 保存/加载，迁移旧 Profile 不丢旧音色。
- 其他 7 种语言的支持须以独立第二阶段实际部署验证为前提，不计入本阶段 PASS。

## 12. 实施纪律

本 SPEC 经独立审计通过后再实施。先补自动化测试，再以最小必要改动实现；先保证 Edge TTS 不退化，再接入 Kokoro；所有新增依赖须说明打包方式。开发完成提交 PR/Commit、测试命令与结果、Mac mini 实测步骤和残留风险；不得以单次 API 成功替代完整验收。