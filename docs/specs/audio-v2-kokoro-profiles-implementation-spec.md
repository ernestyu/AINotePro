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

## 12. 现有 Audio UI 兼容性与纯英语范围冻结（2026-10-29 决策）

本节为**必须实现的 UI 与兼容性约束**，优先于前述章节中可能引起界面重设计或多语言范围扩大的表述。用户已明确决定：**本次 Kokoro 仅做英语，美式和英式均保留；现有 Audio UI 是兼容基线。** “仅英语”只限制新 Kokoro Provider，**不得削减 Edge TTS 现有多语言功能**。

### 12.1 保持现有界面结构和操作习惯

以 `ainotepro/ui/tts_tab.py` 当前 `main` 实现和用户提供的 Audio 标签截图为界面基线。必须保留：
- 顶部 `Generate using` 和 `Language` 两个选择位置；
- 三个纵向排列的 `Voice 1/2/3` 分组，各自独立的 `Enable Voice`、音色下拉框、试听文本框、`Preview` 按钮、`Gender`、`Speed`；Edge 下继续保留 `Volume`、`Pitch`；
- 下方 `Source Field`、`Destination Field`，以及原对话框底部的 `Generate` / `Close` 等主操作；
- 现有滚动区域与 Qt/macOS 原生控件风格；不得为了新增 Kokoro 将三个 Voice 合并为单个音色选择器、改成独立弹窗、移动 Generate 主入口或大规模重排页面。

新增 **Profile 下拉框 + Load / Save / Save As / Delete** 应在 Audio 标签内容顶部使用一行紧凑工具栏，不遮挡或替代原控件；连接状态/Retry 使用简短行内提示，不能增加占满屏幕的服务配置面板。因窗口尺寸或系统缩放造成空间不足时沿用现有滚动区域，避免水平溢出。

### 12.2 Provider 切换与参数映射

| UI 元素 | Edge TTS（兼容基线） | Kokoro MLX（本次） |
|---|---|---|
| Generate using | 保留原 Edge-TTS 选项及语义 | 增加 Kokoro MLX (Local) |
| Language | 保留原多语言列表与选择能力 | 仅 English，显示为固定值或不可编辑选项 |
| Voice 1/2/3 | 原三个区块、启用状态、预览 | **原三个区块与随机选取机制完全保留** |
| Accent | 沿用原 Edge 语言与音色筛选，不强行增加新控件 | **每个 Voice 区块**独立筛选 American / British；不得全局统一口音 |
| Gender | 原 Female / Male | 原 Female / Male；与口音组合过滤可用音色 |
| Voice | Edge 原 ShortName 作为存储值 | 友好标签如 `Heart · American Female · A`，原 `af_heart` 作为存储/API 值 |
| Speed | 原滑块范围与单位不变 | 同位置滑块映射 0.70–1.30 倍，显示实际倍数，切回 Edge 时恢复 Edge 值 |
| Volume / Pitch | 保留原滑块、参数及其值 | **保留位置但禁用**，附简短“不受 Kokoro API 支持”提示；不传给 Kokoro |
| API Key | 现有 Edge UI 行为本次不主动重构 | 隐藏（Kokoro 不需要） |
| Preview | 每个区块原位置、预览该区块 | 同一位置，使用当前区块全部有效参数，不随机、不写 Anki 媒体库 |
| Source/Destination/Generate | 维持现有位置和含义 | 维持相同操作入口，服务未就绪时禁用 Generate |

Kokoro 音色来源以运行时探测到的 28 个英语音色为准，分为 American Female (`af_`)、American Male (`am_`)、British Female (`bf_`)、British Male (`bm_`)；显示名和官方等级来自 `docs/reference/kokoro-official-voice-language-catalog.md`，仅作元数据。建议在每个 Voice 区块现有 `Gender` 所在行紧凑增加 `Accent` 选择框，原 `Voice` 下拉框保留位置，避免将所有音色平铺为不可理解的 ID 长列表。三块可独立选不同口音、性别及音色，随机选择时带走该区块的完整配置。未连接或服务不返回该 ID 时保留 Profile 原值并标记不可用，不自动选第一项。

### 12.3 无损切换、离线及 Profile 恢复

- 切换 Edge ↔ Kokoro 不得将一方的 voice ID、语言、音量、音调、语速数值覆盖到另一方；同名 UI 控件背后须有 Provider 独立的编辑状态或经验证的状态快照。Kokoro 0.95 与 Edge `-5` 等滑块值不能混用。
- 用户选择 Kokoro 后可在下拉框看到当前选择，但后台探测未成功时明确显示 `Checking/Unavailable`，禁用 Preview/Generate 并提供 Retry；**不允许悄悄回退 Edge 并生成音频**。这既满足“不可用就不让用”，也允许加载离线 Kokoro Profile 供编辑和保存。
- Profile 加载与 Provider 切换必须区分：仅明确 Load 才覆盖当前 Profile 的编辑配置；仅切换 Provider 不应覆盖已保存 Profile。未保存状态遵守第 5 节提示规则。
- Edge TTS 现有多语言、语音列表、试听和字段生成流程必须通过回归；即使当前 UI 中出现无意义的 API Key 行，也不得借本次开发删除 Edge 功能或擅自改其持久化语义。

### 12.4 明确排除多语言扩展

本次**不提供**日语、中文、法语、西班牙语、意大利语、印地语或葡萄牙语的 Kokoro 选择项；不修改 Kokoro 模型、Gradio 服务、G2P 安装或音色过滤逻辑；不为非英语 Kokoro 编写可交付 UI。前述第 11 节非英语资料仅作背景参考和未来扩展说明，不是本次实施需求。Profile 可以保留通用 `language/locale` 字段，但不能因此引入第二阶段代码。

### 12.5 必须新增的 UI 回归验收

1. 升级前后的 Edge TTS 顶部控件、三 Voice、语言/性别/音色、Preview、Speed/Volume/Pitch、源/目标字段和 Generate 操作在同一位置且功能等价；原有配置可恢复。
2. Kokoro 只有 English，三个 Voice 独立可混合 American/British、Female/Male；28 个音色 ID 与友好名称/官方等级映射正确，列表不会展示无法合成的其他语言。
3. 在同一窗口反复 Edge → Kokoro → Edge，未保存的两个 Provider 编辑状态与各自滑块值不串用、不被重置；Kokoro 不支持的控件被禁用而非误传参数。
4. Kokoro 离线、连接中、在线、断线、Retry、加载离线 Profile 各状态下，Preview/Generate 的启用条件正确，无静默回退；其他 Provider 正常使用。
5. 保存/加载/删除 Profile、关闭/重开插件后，Provider、口音、性别、原始 voice ID、三个 Voice 的启用和参数、字段均正确恢复；不能因重新填充下拉框导致默认选第一项。
6. Mac mini 实际窗口及不同缩放/窗口尺寸下没有控件重叠、水平溢出或关键按钮不可达；至少对照现有 Audio 截图人工验收。

## 13. 独立审计整改：八项必须冻结的实施契约（2026-10-29）

本节将独立审计要求转换为**规范性、可测试、阻断发布**的契约。与第 3–12 节冲突时，以本节更严格的约束为准；但不得改变第 12 节“**Kokoro 仅英语、原 Audio UI 兼容、Edge 多语言不受影响**”的产品决策。这里是编码要求，不表示依赖兼容、Anki 线程 API 或真实集成测试已经完成。

### 13.1 Kokoro 传输契约（对应审计条款 1）

- **首选**在目标 Anki 内嵌 Python 中实际验证、可随插件发布的 `gradio_client`；开发必须在实现记录中冻结**准确版本、完整传递依赖/锁文件、安装或随包分发方式、许可证及各目标平台兼容性**。不能使用 Kokoro 服务自身 `.venv` 作为 Anki 的运行依赖，不能在 Anki 启动时自动 pip 安装。
- 若改用轻量 HTTP，须单独在**当前真实 Gradio 服务**验证 schema/队列提交/轮询或 SSE/文件下载/异常路径，保留端到端可复现证据；仅能证明普通 `POST` 可连通不算通过。未经验证不得替换 `gradio_client`。
- 当前唯一已实测 API：`/synthesize`，入参 `text: str`、`voice: str`、`speed: float`；**三个按位置返回值**为 `Audio MP3 文件`、`下载文件`、`状态文本`。客户端必须校验三元组数量、类型、音频与下载文件可访问性；读取第一个音频结果为本次合成产物，第二个用于一致性/可用性校验，第三个只用于诊断，**不得将状态字符串当作成功的唯一证据**。不假设 API 直接返回 MP3 bytes，也不假设服务端路径在插件进程中天然可访问；须通过客户端实际下载路径读取。
- 探测须验证服务身份、端点与入参/出参 schema、可用音色及本机 URL；**不触发真实合成**。发现音色必须与 `af_/am_/bf_/bm_` 的英语范围求交集；返回无有效英语音色即不可用。
- 每次探测/生成必须有**有限**连接、排队、合成、下载和整体截止时间；推荐初始上限：探测 10s、排队 120s、合成+下载 300s、整个单条任务 420s，实际 API 如不能分别施加截止时间则须采用可取消/可放弃结果的受控 worker 和整体 watchdog，绝不能在 UI 线程等待。重试必须有限（默认不自动重试可能重复执行的合成请求）；队列拒绝、429、服务断线、超时、版本不兼容、schema 漂移、下载失败分别归类并展示可操作的错误。
- 客户端取得的 MP3 必须存在、非空、有合理文件大小上限，并通过**真实 MP3 解码/探测或等价的结构验证**；仅文件扩展名或 `ID3` 头不足以证明可播放。转换为 `bytes` 后仅清理**插件自己创建**的下载副本/临时文件，不能删除 Gradio 管理的缓存或服务端 `output/`。失败不产生 Anki 字段写入。发布时要记录已验证的服务端和客户端版本组合；发现不兼容必须阻断 Kokoro 生成而非降级到 Edge。

### 13.2 Audio Profile JSON Schema 与持久化（对应审计条款 2）

**规范数据结构**：`user_files/user_config.json` 下的 `audio` 为版本化域，`audio.profiles` 是**整体替换域**（禁止递归合并）。每个 Profile 的稳定 ID 为 `profiles` 的 key，显示名称可编辑，ID 不因改名改变。每个 Profile 保存所选 `provider`，以及两个 Provider **各自独立**的三 Voice 配置，以便切换后恢复各自未保存编辑；同时保存字段选择。配置示例和 JSON Schema 采用 JSON Schema Draft 2020-12（如下）。音色可用性由在线探测判断，不得因为服务离线而使结构校验失败或丢失原始 voice ID。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AINotePro Audio V2 config domain",
  "type": "object",
  "required": ["schema_version", "profiles", "last_profile_id", "migration"],
  "properties": {
    "schema_version": {"const": 2},
    "last_profile_id": {"type": ["string", "null"]},
    "migration": {
      "type": "object",
      "required": ["legacy_edge_v1_done"],
      "properties": {"legacy_edge_v1_done": {"type": "boolean"}},
      "additionalProperties": true
    },
    "profiles": {
      "type": "object",
      "minProperties": 1,
      "propertyNames": {"pattern": "^(legacy-edge-default|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"},
      "additionalProperties": {"$ref": "#/$defs/profile"}
    }
  },
  "additionalProperties": true,
  "$defs": {
    "voice_edge": {
      "type": "object",
      "required": ["enabled", "voice", "gender", "speed", "volume", "pitch", "preview_text"],
      "properties": {
        "enabled": {"type": "boolean"},
        "voice": {"type": "string"},
        "gender": {"enum": ["Female", "Male"]},
        "speed": {"type": "integer", "minimum": -50, "maximum": 50},
        "volume": {"type": "integer", "minimum": -50, "maximum": 50},
        "pitch": {"type": "integer", "minimum": -50, "maximum": 50},
        "preview_text": {"type": "string"}
      },
      "additionalProperties": false
    },
    "voice_kokoro": {
      "type": "object",
      "required": ["enabled", "voice", "accent", "gender", "speed", "preview_text"],
      "properties": {
        "enabled": {"type": "boolean"},
        "voice": {"type": "string", "pattern": "^(|(?:af|am|bf|bm)_[a-z0-9_]+)$"},
        "accent": {"enum": ["American", "British"]},
        "locale": {"type": "string", "enum": ["en-US", "en-GB"], "description": "Optional voice-level locale; default derived from accent."},
        "gender": {"enum": ["Female", "Male"]},
        "speed": {"type": "number", "minimum": 0.7, "maximum": 1.3},
        "preview_text": {"type": "string"}
      },
      "additionalProperties": false
    },
    "profile": {
      "type": "object",
      "required": ["schema_version", "name", "provider", "source_field", "destination_field", "random_strategy", "provider_configs"],
      "properties": {
        "schema_version": {"const": 2},
        "name": {"type": "string", "minLength": 1, "maxLength": 100},
        "provider": {"enum": ["edge_tts", "kokoro_gradio"]},
        "source_field": {"type": "string"},
        "destination_field": {"type": "string"},
        "random_strategy": {"const": "uniform_per_note"},
        "provider_configs": {
          "type": "object",
          "required": ["edge_tts", "kokoro_gradio"],
          "properties": {
            "edge_tts": {
              "type": "object",
              "required": ["language_code", "voices"],
              "properties": {
                "language_code": {"type": "string", "minLength": 1},
                "voices": {"type": "array", "minItems": 3, "maxItems": 3, "items": {"$ref": "#/$defs/voice_edge"}}
              },
              "additionalProperties": true
            },
            "kokoro_gradio": {
              "type": "object",
              "required": ["base_url", "language", "voices"],
              "properties": {
                "base_url": {"type": "string", "format": "uri", "pattern": "^http://(127\\.0\\.0\\.1|localhost)(:[0-9]+)?/?$"},
                "language": {"const": "en"},
                "voices": {"type": "array", "minItems": 3, "maxItems": 3, "items": {"$ref": "#/$defs/voice_kokoro"}}
              },
              "additionalProperties": true
            }
          },
          "additionalProperties": false
        }
      },
      "additionalProperties": true
    }
  }
}
```

**`locale` 契约（P1-01）**：`locale` 定义在**每个 Kokoro Voice 区块**而非 Provider 顶层，允许同一 Profile 混合美式和英式。字段可选，以兼容已保存的 V2 Profile；缺失时从该区块 `accent` 推导默认值（`American → en-US`，`British → en-GB`），新建或重新保存时显式写出。当前只允许 `en-US` / `en-GB`，Provider `language` 固定 `en`。应用层必须核验 `locale`、`accent`、`gender` 和 voice ID 前缀一致（`af/am → en-US`、`bf/bm → en-GB`）。**结构校验与运行时音色可用性校验必须分离**；离线或音色不再可用不能导致合法 Profile 无法加载。

**结构之外的业务校验**：Profile key 采用小写 UUID v4（迁移 Profile 固定 `legacy-edge-default`）；Profile 名称去首尾空格后非空，同名（大小写不敏感）拒绝或明确提示重命名；`last_profile_id` 为 `null` 或存在于 `profiles`；三个 Voice 的 ID、口音、性别必须相互一致，允许空 voice 仅用于禁用的未配置区块；实际启用区块必须有可用 voice。URL 必须再做运行时 loopback 校验（含 DNS/重定向），不能只信 schema 正则。字段名允许空字符串作为尚未选定状态，但生成前必须验证存在。默认：Provider `edge_tts`、Edge 语言 `en`、三块均禁用、Edge 速度/音量/音调为 0、Kokoro 速度 1.0、Kokoro URL `http://127.0.0.1:7860`、策略 `uniform_per_note`；默认 Preview 文本为空。具体默认音色可从现有 Edge 配置恢复，不得臆造用户旧设置。

**完整 Audio V2 JSON 实例（P1-01）**：以下是 `user_config.json` 中的 `audio` 域，真实文件还包含独立的 `text/ui` 域。三个 Voice 区块均保存，即使未启用也保留其参数。

```json
{
  "schema_version": 2,
  "last_profile_id": "123e4567-e89b-42d3-a456-426614174000",
  "migration": {
    "legacy_edge_v1_done": true
  },
  "profiles": {
    "123e4567-e89b-42d3-a456-426614174000": {
      "schema_version": 2,
      "name": "English practice",
      "provider": "kokoro_gradio",
      "source_field": "Sentence",
      "destination_field": "Audio",
      "random_strategy": "uniform_per_note",
      "provider_configs": {
        "edge_tts": {
          "language_code": "en",
          "voices": [
            {
              "enabled": true,
              "voice": "en-US-AriaNeural",
              "gender": "Female",
              "speed": 0,
              "volume": 0,
              "pitch": 0,
              "preview_text": ""
            },
            {
              "enabled": false,
              "voice": "en-GB-SoniaNeural",
              "gender": "Female",
              "speed": 0,
              "volume": 0,
              "pitch": 0,
              "preview_text": ""
            },
            {
              "enabled": false,
              "voice": "en-US-GuyNeural",
              "gender": "Male",
              "speed": 0,
              "volume": 0,
              "pitch": 0,
              "preview_text": ""
            }
          ]
        },
        "kokoro_gradio": {
          "base_url": "http://127.0.0.1:7860",
          "language": "en",
          "voices": [
            {
              "enabled": true,
              "voice": "af_heart",
              "accent": "American",
              "locale": "en-US",
              "gender": "Female",
              "speed": 0.95,
              "preview_text": ""
            },
            {
              "enabled": true,
              "voice": "bf_emma",
              "accent": "British",
              "locale": "en-GB",
              "gender": "Female",
              "speed": 1,
              "preview_text": ""
            },
            {
              "enabled": true,
              "voice": "am_adam",
              "accent": "American",
              "locale": "en-US",
              "gender": "Male",
              "speed": 1.05,
              "preview_text": ""
            }
          ]
        }
      }
    }
  }
}
```

**独立验证要求**：使用 `jsonschema.Draft202012Validator.check_schema(schema)` 校验仓库原文的 Schema，再以 `Draft202012Validator(schema, format_checker=FormatChecker()).validate(example)` 校验实例。反例应覆盖非法 locale、非英语、超范围速度、非三个 Voice、非法 Profile ID；省略可选 locale 的合法旧 Profile 应通过结构校验并由应用层补默认值。另测 locale/口音/性别/前缀一致性、离线失效音色仍可加载、`last_profile_id` 指向现有 Profile。必须记录校验器版本与结果；JSON 解析成功不等于 Draft 2020-12 验证通过。

**迁移优先级与删除**：
1. 已有合法 `audio.profiles` 为权威，保留其稳定 ID 和内容；绝不因仍存在 `audio.edge_tts` 再创建默认 Profile。
2. 尚无 Profiles 且 `migration.legacy_edge_v1_done` 不为 true 时，读取现有 `audio.edge_tts`，生成**恰好一个** `legacy-edge-default` Profile；只迁移实际存在的值，缺失部分按上述默认填充，并在同一次原子提交中写迁移标记。
3. 既无可迁移旧配置也无 Profiles 时，初始化一个默认 Edge Profile；迁移标记为 true。已有迁移标记而 Profiles 缺失/无效时视为配置损坏，**不得重建已删除 Profile**，进入明确的恢复流程。
4. 删除一个 Profile 必须从整个 `profiles` 映射中删除；禁止默认递归合并将其复活。不得删除最后一个 Profile；删除当前 Profile 后将 `last_profile_id` 置 `null` 并要求显式选择/加载其他 Profile，不暗中覆盖当前编辑。失效 `last_profile_id` 同样置 `null`，提示用户选择，不自动加载第一项。

**存储事务**：所有 Profile/迁移/last ID 变更必须经唯一 `ConfigManager` 读改写接口；`audio.profiles` 整体替换，其他 `text/ui` 与未知旧键保留。单进程写入序列化并在提交前检查配置修订版本，避免两个窗口或模块互相覆盖。写入同目录临时文件，完整序列化并校验、flush/fsync 后用 `os.replace` 原子替换，支持时同步父目录；任何失败保留旧文件并清理临时文件。JSON 解析失败、schema 校验失败、未来不认识的 schema_version：**只读报错、保留原始文件、禁止覆盖**；可让用户选择备份文件并手工恢复，不能静默初始化。对老配置迁移前保留一次原始备份；不在日志输出 API Key 或其他 Text 配置秘密。

### 13.3 Provider / Profile / UI 三状态机（对应审计条款 3）

状态必须分开存储，禁止混用：
- **持久化 Profile**：`profile_id`、`saved_revision`、`last_profile_id`；
- **当前 UI 草稿**：`draft_profile`、`dirty`、`draft_revision`（仅 Save/Save As 写盘；切换 Provider 只改草稿，未保存需按第 5 节提示）；
- **Provider 健康**：`unprobed | checking | ready | unavailable`，以及 `probe_request_id`、`base_url`、`provider`、`draft_revision` 快照。

任何后台探测响应必须校验**请求 ID、窗口仍存活、Provider/URL/草稿版本仍匹配**才可改变当前 UI 健康状态；过期响应只能丢弃，不能覆盖新加载 Profile、新选择 Provider 或新 URL。Kokoro 离线仍可 Load/编辑/Save/Save As/Delete，Preview/Generate 不可用；不允许静默切换 Edge 继续生成。Edge 的健康状态不依赖 Kokoro。开始生成时冻结 Provider、URL、每个有效 Voice 的完整参数、源/目标字段、note IDs 与策略；批次运行中用户修改 UI 不得改变已启动任务。取消后不得把迟到结果提交给笔记。

### 13.4 三 Voice 完整参数随机与 Preview（对应审计条款 4）

每张笔记从**已启用且 Provider/语言/口音/性别/voice ID/参数均合法的 Voice 区块**中做一次均匀抽样，抽中的是完整不可变区块快照（含 voice、speed、volume/pitch〔仅 Edge〕、accent、gender），**禁止分别抽 voice 与 speed**。每张笔记独立抽取；同音色在两个区块中出现仍按两个区块计权。零有效区块直接阻断批次并报告。Preview 指定第 1/2/3 区块，不随机；使用该区块当前速度等全部有效参数；不进入 Anki media。将随机源注入可单测的纯函数，固定随机序列核对参数配对，另以足量样本及预设容差检查分布，不把概率测试作为唯一正确性证据。

### 13.5 Anki 后台任务与提交协议（对应审计条款 5）

1. Qt 主线程获取**有限**的 note ID、源文本/字段名、目标字段内容指纹、音色与 Provider 快照；网络探测、合成、下载、MP3 校验只在后台进行。后台任务不得访问 Qt 控件或 `mw.col`，不得持有/操作 Anki note 对象。
2. 采用目标 Anki 版本**实际支持**的任务管理与 collection 操作/撤销 API（须在 Anki 26.05+ 实机核验，不能凭旧版示例臆测）；UI 进度与提交经主线程安全回调。批次初版并发度 1，限制预取和内存；不得在主线程 `join` 或同步等待。
3. **提交前在合法 collection 上下文重新读取笔记**，验证 note 存在、笔记类型、源/目标字段存在、源内容或其指纹未变、目标字段内容与启动时快照一致、未被其他任务写入声音；不一致归类 `conflict_skipped`，不能覆盖用户编辑。
4. 正式提交顺序：验证 → 写入 Anki 媒体库取得文件名 → 构造精确 `[sound:filename]` → 按目标 Anki 的可撤销写入机制更新 note → 校验 note 提交成功 → 写入/更新来源记录。媒体写入成功而 note 更新失败，结果为 `failed_commit`，**不得产生悬空字段引用**；可留下未引用媒体但不自动删除（可能共享），应记录供人工诊断。来源记录写入失败时必须报告 `failed_provenance`，禁用后续自动 Replace，不能宣称完整成功。
5. Cancel 立即停止派发新笔记；正在合成的请求可完成但取消后**不得提交**。窗口关闭/销毁时废弃旧 UI 回调；后台结果仍须遵循取消与提交门禁。防止重复点击/并发批次，明确同一 note 的互斥或版本检查。
6. 每张笔记结果使用固定枚举：`success`、`skipped_empty`、`skipped_existing_audio`、`skipped_invalid_fields`、`conflict_skipped`、`cancelled`、`failed_probe`、`failed_synthesis`、`failed_download`、`failed_validation`、`failed_commit`、`failed_provenance`。统计与用户可见结果一致；单笔失败不回滚先前成功。必须验证撤销/重做及浏览器/编辑器入口的笔记刷新行为。

### 13.6 幂等、来源记录与 Replace（对应审计条款 6）

- 默认 **Skip**：目标字段只要存在任何有效 `[sound:...]` 引用即跳过该笔记；无论该声音是否由本插件生成。无声音时保留既有文字/HTML，再追加唯一音频引用；重复 Generate 不追加。
- **来源记录**存于 `user_files` 下由统一管理器维护的独立版本化索引（例如 `audio_provenance_v1.json`），每条至少包含 `schema_version=1`、`note_id`、`destination_field`、`media_filename`、`media_sha256`、`sound_tag`、`provider`、`created_at`。以 `note_id + destination_field + sound_tag` 作为记录匹配键；写入应为原子替换，保留失败诊断，不能靠文件名前缀猜测所有权。记录不包含全文源文本、API Key 或临时路径。
- **Replace 门槛**：明确开启 Replace 后，必须同时验证来源索引命中、目标字段含有**完全匹配**的原声音标签、媒体文件仍存在且 SHA-256 一致、没有歧义的重复标签、当前字段内容未在后台生成期间变化。任一条件不满足则保守跳过并提示人工处理；绝不能用 `ainotepro-` 文件名前缀或正则批量清理未知音频。替换只移除该条已验证旧标签并添加新标签，保留字段其余内容/HTML 和其他声音引用。
- 来源记录写入失败或配置丢失时：已生成声音仍可通过 Anki 同步播放，但该音频被视为**不可自动 Replace**。撤销/重做、手动编辑、笔记删除、媒体重命名后，旧索引可能失效；下一次 Replace 必须实时核验并保守拒绝，不得以旧索引作为最终证据。跨设备同步仅保证 Anki 字段和媒体；`user_files` 的来源索引不视为跨设备共享数据，其他设备无记录时默认 Skip。禁止自动删除 Anki 媒体文件。
- 源/目标同字段：必须显式风险确认，合成文本先清除 HTML 与已有声音标记；提交前再次验证字段指纹。旧版未知来源音频不作自动归属。音频生成失败、取消或冲突时不应改变字段。

### 13.7 入口封闭、Edge/Text 兼容（对应审计条款 7）

必须清点并测试 `TTSTab.on_generate_tts()`、`AIManager.generate_audio_for_field()`、`MainDialog`、编辑器/浏览器钩子及其他所有可触发音频写入的入口。所有**可达**音频入口必须调用同一个安全的生成/提交编排层，执行同样的音色选择、Skip/Replace、provenance、线程、撤销规则；若某旧入口不再支持，必须显式禁用或转发，**不能留下可绕过保护的旧实现**。不得改 Text 业务接口，Edge 原有 Provider API、语言范围和 Audio UI 位置保持兼容。Audio 默认语言改为 **English**（不再默认 Afrikaans）；无意义的 API Key 控件在 Edge/Kokoro 下隐藏或禁用，但不得影响 Text Provider 的凭据配置。目标 Anki Python 环境、macOS Apple Silicon 与所有声明支持的发布平台必须实测依赖安装/导入；未验证平台不得标记支持。

### 13.8 测试矩阵与发布门槛（对应审计条款 8）

- **自动化**：JSON Schema 校验/缺省/损坏/未来版本、旧 Edge 配置迁移优先级/幂等/删除不复活/原子写失败；随机种子和参数配对/分布；Provider 切换和过期探测竞态；Gradio 三输出/排队/超时/版本不兼容/下载损坏；主线程提交前冲突检查；Skip/Replace 来源验证/撤销/重复生成；Preview 临时文件清理；取消、窗口销毁、批次失败隔离；两条音频入口同一安全策略；Edge/Text 回归。
- **真实 Anki**：在目标 Anki 26.05+ 的内嵌 Python 验证依赖；Mac mini Apple Silicon 真实 `/synthesize`；1/10/100 张笔记；Edge/Kokoro、Kokoro 离线→Retry→恢复、Profile 保存→退出→重启、旧 user_files 升级、Preview 不增加媒体、重复生成 Skip、Replace 只处理确证归属音频、Cancel/关闭/重复点击、撤销/重做、浏览器/编辑器入口、Anki 媒体同步到手机播放；检查现有 UI 截图对照和纯英语范围。
- 每个验收项记录环境、版本、命令/操作、实际结果和证据；未执行标记 `NOT TESTED`，失败标记 `FAIL`，**不得用 mock PASS 代替真实端到端证据**。任一必需真实验收项 `FAIL`/`NOT TESTED` 时不得宣称发布通过；仅可说明当前阻断项及受限测试结论。任何非目标平台未验证，须在发布声明中排除该平台或阻断跨平台发布。

## 14. 实施纪律

本 SPEC 经独立审计通过后再实施。先补自动化测试，再以最小必要改动实现；先保证 Edge TTS 不退化，再接入 Kokoro；所有新增依赖须说明打包方式。开发完成提交 PR/Commit、测试命令与结果、Mac mini 实测步骤和残留风险；不得以单次 API 成功替代完整验收。