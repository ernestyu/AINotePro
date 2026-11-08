# AINotePro V1.2.0 — Text Advanced 多笔记打包生成 SPEC（FROZEN）

状态：**FROZEN — 设计合同已冻结，代码尚未实施**。第三方静态审计结论：PASS WITH MINOR（审计基线 `2fd2fe3f41047fc0173fc13533e3d42bfcac7f96`）；本次仅修正审计指出的外层批次激活边界，未修改其他产品决策。运行测试仍待开发阶段执行。  
仓库：`ernestyu/AINotePro`  
实施基线：`feature/prompt-library-github-sync`，Commit `dbc02526d30628f0479608a558c0b628ccb17fa1`（在本实施分支上纳入冻结 SPEC）  
范围：仅 Text Advanced 多笔记 LLM 请求与配套 UI、解析、重试、测试；不包含本 SPEC 的实现提交。  
设计冻结源 Commit：`6f4aff17e4321a3ad9d4319a88ef5c28a6901895`。新基线的 Endpoint URL 与日志脱敏实现以 `dbc0252` 的源码为准；本 SPEC 的 Provider 结构化错误分类仍须实施。  
上位合同：现有 `docs/specs/2026-11-01-text-advanced-multifield-generation-SPEC.md` 中的字段、Prompt、预检、存储与安全写入约束；冲突处以本文件对「多笔记请求协议」的显式修改为准，其他条款不变。

## 1. 产品目标与边界

用户选中 N 条属于同一 Note Type 的笔记时，Text Advanced 可以把同一批内最多 B 条的已验证源字段与目标字段指令打包为 **一次**模型请求；单次输出可含多条独立有效答案。若只返回部分有效记录，接受有效项，仅对当前小批次的未完成项重新请求；当前小批次完成后才开始下一批。B 由用户手工选择，绝不自动查询或推断模型上下文长度。

明确不做：修改 Text Easy；更改 Easy 的固定单 Worker、OCR、生成行为；改动 Audio；自动上下文发现、自动 token 预算、自动调整 B；跨批次并发、流式逐 token 写回；在 GitHub 或其他远端保存笔记内容；自动修改用户 Prompt 以适应不兼容的模型；无边界无限重试。

**Batch Size = 1** 必须保持当前 Advanced 的单笔记请求格式、`compile_prompt()` 和 `parse_response()` 语义，不经过多笔记 JSONL 协议。Batch Size > 1 启用新协议。无论 B 为多少，Advanced 的字段选择、Prompt 声明和写入安全合同一致。

## 2. 冻结基线核对（实施人必须重新确认）

- `ainotepro/ui/text_tab.py`：`GenerationWorker.run()` 固定 `max_workers = 1`，属于 Easy 普通文本执行路径；不得改动。Easy 图像识别另有逐笔记执行路径。
- 同文件 `AdvancedGenerationWorker.run()` 当前依次调用 `provider.generate(compile_prompt(...), config)`，每条笔记一次；返回当前单笔记 JSON，通过 `parse_response()` 校验。
- 同文件 `_build_ui()` 底部 Field Mapping 行原有 `Image Recognition` Checkbox；`_update_field_mode_widgets()` 在 Advanced 隐藏它（`setVisible(not advanced)`），在 Easy 显示。
- 同文件 `_start_advanced_generation()` 在任何模型请求前执行 Note Type/字段/Prompt/输入内容整批预检，确认覆盖风险，固定 provider/model 配置快照；当前使用 Qt 后台 worker。
- 同文件 `_finish_advanced_requests()` 当前在 worker 完成后汇总有效结果，并经 `_commit_advanced_results()` 的单个 `CollectionOp` 提交；`_handle_advanced_commit_result()` 与 `AdvancedBatchLedger` 负责结果统计。
- `ainotepro/core/advanced_text.py`：`validate_prompt`、`compile_prompt`、`preflight_requests`、`parse_response` 与 `snapshot_matches` 属于现有合同；`parse_response` 是单笔记严格 JSON，不适合直接解析 JSONL。
- `ainotepro/core/advanced_commit.py`：`commit_validated_results` 在串行 CollectionOp 中重读每张笔记，验证快照，逐笔记完整写入所有目标字段，创建/合并 Undo；某些写入或 Undo 异常具有不可确定性，绝不能自动重试写入。
- `ainotepro/core/advanced_ledger.py`：每个所选 Note ID 必须归入一个确定的最终状态；现有 `record_worker` 的一次性终态语义必须针对新 worker 的多轮重试调整，不能把首次 JSON 失败永久登记后阻止后续成功。

上述基线只是静态源码判断，不表示已执行任何运行测试。

## 3. UI 与配置合同

仅在 Text 页面底部**现有** `Image Recognition` 所占的 Field Mapping 行位置显示：

`Batch Size: [10 ▼]`

- Advanced：显示 Label 和一个紧凑、不可编辑的 `QComboBox`，选项为连续整数 1–20，默认 10。不加加减按钮、解释文字、单独行、常驻状态卡片或滑杆；尽量保持原对话框高度。
- Easy：完全隐藏 Batch Size Label/Combo，保留并显示原有 `Image Recognition`；切换模式不重置 Easy Checkbox 的既有选择。
- 配置字段固定为 `text.advanced_batch_size`，整型，缺失、非法、布尔、超出 1–20 的旧配置统一读取为 10；只读时不强制覆写旧文件。必须把此键加入 `ConfigManager.update_text_fields()` 的**有限白名单**；写入时只接受 `type(value) is int` 且 `1 <= value <= 20`，非法 UI/外部写入明确拒绝。使用现有锁和原子写入做 Text 叶子键局部更新，保留 Prompt CAS、Provider、Audio、未知键和凭据；UI 保存失败需提示，并将控件恢复为最后确认持久化的值，不得静默声称成功。
- 开始生成时冻结 B；运行中禁用 Batch Size、Prompt Preview 编辑区、Prompt Name/Search、New/Save/Save As/Delete、Import/Export、GitHub Save/Load/Settings、Mode、Source/Destination、Resolve、Provider/Model/Reasoning/Endpoint/Temperature/Refresh/Check/Restore 及 Generate；保留进度窗口 Cancel。执行前冻结全部输入和设置，不允许运行中的界面更改污染快照。已有控件的启用/禁用能力状态（例如权限、默认 Prompt 保护、Provider 能力）必须在解锁后**重新计算**，不能统一 `setEnabled(True)`；关闭/取消/错误/提交完成只能由当前 run_id 对未销毁控件恢复。Easy 不受此新增锁定规则影响。
- Advanced 模式下 Checkbox 的隐藏状态绝不影响 OCR 后端分支；`on_generate_text()` 仍优先分派 Advanced。
- 不增加 UI 上的上下文长度说明。明确的上下文/输出限制拒绝在最终错误弹窗里附加中文提示：**“超出模型上下文或输出限制时，请减小 Batch Size。”** 其余故障不能被错误标记为上下文溢出。

## 4. 单批执行与调度定义

输入是一组 **按首次选择顺序稳定排序、去重后的** NoteSnapshot；必须在启动任何请求前完成现有全选集预检与覆盖确认。设全选集序列 S，冻结 B。

定义 **外层批次**：顺序从 S 预选下一个最多 B 个尚未调度的 Note ID，但**预选本身不激活批次**，不从 `not_started` 移走笔记。首次 Provider 请求真正开始时，原子性地激活本批：登记 `current_batch_ids` 和本次 `current_batch_requested_ids`，将该批全部 ID 由 `not_started` 移入 `current_batch_pending`，并令 `no_progress = 0`。在请求发起前取消或失败，待预选 ID 仍全属 `not_started`，活动批的三个集合均为空。已激活的外层批不与下一批交错，也不并发；每次后续模型调用只含本批剩余 `pending` 中的所有 ID（原始稳定顺序），并在实际请求开始前更新请求登记。`accepted` 是整个运行范围内累计的有效项，而非每批重新清空。

对一次调用的完整返回做独立记录解析和身份校验，得出新有效集合 `valid_new`：
- 若 `|valid_new| > 0`，把这些 ID 的整条输出加入 `accepted`，移出 `pending`，`no_progress = 0`。
- 若 `|valid_new| = 0`（包括响应无有效行、只有无效/重复记录、无可用响应、可恢复的调用错误），`no_progress += 1`。
- 若 `pending` 已空，当前外层批次结束，再从 S 取下一批最多 B 条。**新一批的大小仍为 B**，不因上一批的重试余量而改变。
- 若 `no_progress == 3`，停止**整个** Advanced 生成任务（不仅当前批），不再开始任何后续外层批次；保留此前已接受的有效模型结果，按 §7 安全提交可提交部分并报告剩余未完成数。无进展计数仅属于**当前未完成外层批**，新批重置；任何新的有效项都清零。
- 某个外层批最多 B 个新有效项；每次有进展必严格减小 pending，因此一个成功完成的外层批至多 B 次有进展的调用，中间可以夹杂最多 2 次连续无进展调用；不额外设置“每条笔记最多 3 次”限制。
- 原始 Snapshot、provider/model/Prompt、sources/destinations 和 B 均在运行开始冻结；失败重试不得再次读取 Anki 或把已经生成的目标字段回填成输入。worker 不直接接触 Collection、Note 或 QWidget。

**异常优先级**：用户取消、明确的上下文或输出预算服务端拒绝、认证/权限错误、无效模型或 Endpoint、不可继续的线程/进程异常，均应直接停止整个任务，不重复同一个不可恢复请求。**Provider 错误结构**：`generate(prompt, config)` 成功仍返回原样字符串；失败抛出含 `category`（`context-or-output-limit`、`auth`、`invalid-model-or-endpoint`、`retryable`、`unknown`）、可选整数 `http_status`、安全有限的 `service_code` 和固定 `safe_summary` 的异常。`_diagnostics.request_failed()` 及 OpenAI-compatible/Ollama `_request()` 需在吞并原始异常前归一化该信息；只从可信 HTTP 状态和**已解析的结构化服务端错误码/字段**映射，不依赖模糊消息关键词；普通 HTTP 400 不自动当上下文超限。401/403 归 auth；明确的模型/路由缺失归 invalid-model-or-endpoint；429、5xx、超时/暂时网络失败归 retryable；未识别类别归 unknown，并按保守零进展策略计数（但不得无限重试）。不扫描或向外展示原始请求体、响应体或包含敏感数据的异常文本。`safe_summary` 使用受控模板，`service_code` 白名单字符且限制长度；可展示的服务端细节必须脱敏和截长（建议 160 字符上限），任何不可信原始错误直接省略。网络超时等未收到有效响应的调用视为零进展，不计入 accepted；三次后停止。适配器修改须有 Easy/OCR 行为回归测试。

**上下文错误**：仅依据明确可识别的服务端上下文容量/输出预算拒绝而分类；发现后立即停止，不做自动缩批、模型查询、隐式 token 截断；仅展示 Provider 产生的**脱敏、截长、受控 `safe_summary`**，绝不直接展示服务端原始错误正文，并附加指定提示。若响应只是不完整/截断 JSONL，**无需检测或推断截断原因**，按 §5 接受完整有效记录，重发未完成项。

## 5. 多笔记请求及 JSONL 输出协议（B > 1）

### 5.1 输入生成

仍使用现有 `validate_prompt` 的字段集合、声明顺序及字面大括号转义，**不得重新解释用户 Prompt 语法**。**B>1 不能直接调用现有 `compile_prompt()` 作为单条指令**：该函数会追加“返回单个 JSON 对象”的输出后缀，与 JSONL 冲突。必须增加独立的批处理指令编译入口（例如 `compile_batch_instruction(parsed, input_values)`），复用同一 AST 的全局/目标字段段落渲染，但不附加单笔记 JSON 结束指令；仅批处理层在全部结构化输入外统一追加 JSONL 协议。B=1 继续直接调用未经更改的 `compile_prompt()` 和 `parse_response()`，生成的完整 Prompt 文本必须与基线逐字符相同。每张笔记的已编译指令是彼此独立的数据单元；不得让模型把一张笔记的输入作为另一张的上下文。将指令连同 Note ID 编成明确、有长度/边界的结构化输入（建议序列化为 JSON 数组，每项含 `note_id` 与 `instruction` 字符串，`json.dumps(ensure_ascii=False)`），确保含换行、引号、JSON、控制字符或伪 Note ID 的笔记文本不会破坏分隔符。

插件附加固定批处理协议指令，要求**仅返回 JSONL**：每条完成的笔记占**一行独立完整 JSON 对象**，不需要外层数组、Markdown 代码围栏或解释文字。每条记录形如：

~~~json
{"note_id":"12345","fields":{"Translation":"翻译结果","Note":"说明结果"}}
{"note_id":"12346","fields":{"Translation":"另一条翻译","Note":"另一条说明"}}
~~~

`note_id` 是十进制字符串形式的真实 Anki Note ID，**仅作为匹配键**，不是写入时的授权证据。`fields` 内目标字段名必须与当前 Advanced 已选择的目标字段集合严格相等，值须为非空合法字符串。不得从输出行的顺序推断笔记身份。JSONL 文本一行一个完整对象；输出字段内容中的换行必须被 JSON 字符串转义，不得产生物理跨行记录。

### 5.2 解析及部分接受

在一次**完整收到的响应文本**上先做全量、按物理行独立解析，然后才确定这次哪些 ID 有效；不得读到第一条有效行就立即提交 Anki。解析器为纯 Python、Qt/Anki 无依赖，采用确定行为：

1. **冻结限额：完整收到的响应字符串按 UTF-8 编码后总长度不得超过 20 MiB，单个物理行不得超过 1 MiB**（B≤20，每条对应原单条 1 MiB 校验量级）。先按一次完整响应计算总字节长度；若总长度 >20 MiB，**整次响应 0 条接受**、计作零进展，并报告 `response-too-large`，不得截取前缀或部分扫描。若总长度在限额内，则按原始物理行顺序扫描全部行；超过 1 MiB 的单行直接判无效，继续检查后续完整行。`==` 上限允许，`>` 上限拒绝。仅完整、通过全部规则的行可接受；不得把因为长度上限而未检查的内容声称已完成。模型自行返回的不完整尾行按普通坏行处理。
2. 对每条物理行分别 `json.loads()`；空行、模型说明、损坏行或最后一条半截 JSON 不导致整份响应失败。保留其他可验证行。可选择严格拒绝非 JSON 行，不尝试危险的跨行拼接或启发式修复。
3. 反序列化使用 `object_pairs_hook` 拒绝重复键（包括顶层与 `fields`），拒绝 NaN/Infinity、非对象、缺少或多余固定顶层键、错误 ID 类型、非法字段集合、空白字符串与非法代理 Unicode；**允许经 JSON 正确转义的 `\n`、`\t` 等字段内容**，与基线 Advanced 多行输出兼容。非法原始 JSON 控制字符由严格 `json.loads()` 拒绝；不得笼统拒绝所有可打印性不高的合法字符串。Note ID 必须规范十进制字符串，与本次 `pending` ID 严格匹配；不接受当前批之外、未知、上批已接受或下一批 ID。
4. **同一个 Note ID 在同一完整响应出现两次或多次时，该 ID 本次无效**，即使其中一条字段值/字段集合非法；ID 出现次数只对“在单行限额内、可完整 `json.loads` 为对象、顶层 `note_id` 是规范十进制字符串”的行统计（该行的 `fields` 可无效）。重复顶层 JSON 键导致整个对象解析失败时，该行不能用于统计 ID；损坏行、超长行、无法安全解析 ID 的行均不得通过正则或局部文本猜测 ID。先全量扫描完成 ID 次数表，再决定有效结果；绝不“取第一条”或“取最后一条”。
5. 一个 Note ID 的 **所有** Destination 必须同时通过验证，才算一条新有效结果；禁止部分字段通过就写入，亦不得用上一轮失败的部分字段拼装新结果。
6. 如果模型返回 B 条中的 8 条完整合法记录、1 条无效、1 条缺失，接受 8 条，下一次只发送另 2 条。无需解析“是否达到输出 token 上限”。
7. 模型内容不能触发源码执行、额外网络请求或字段改名；返回的 HTML 等字段内容按现有 Advanced 输出与 Anki 写入策略处理，不以单条响应来改变保存策略。
8. 明确记录可安全暴露的计数和简短原因码；不得把输入 Prompt、笔记正文、完整响应或 API Key 打进普通诊断日志。
9. **信任边界：** 用户 Prompt 和字段文本可以含 JSON、换行、伪造 Note ID 或指令，但在批处理外层协议中全部作为 `instruction` 字符串数据进行 `json.dumps(ensure_ascii=False)` 转义。插件固定的输出协议是唯一权威约束；任何嵌入输入文本的“更改 ID/改用数组/输出其他字段”等请求都不能改变校验。模型自报 Note ID 只用来比对本次 pending，不是授权；不在本次集合中的记录永远不写入 Anki。

### 5.3 B = 1 的兼容合同

不创建 JSONL；严格保留目前 `compile_prompt()` 的单笔记提示及 `parse_response()` 的单 JSON 对象格式；保留相同来源/目标语义、异常与字段约束。新的调度器可以统一管理进度和三次无进展，但 **B = 1 不能改变模型看到的输入/输出协议**。明确回答：选为 1 是保守兼容路径，而非新的 JSONL 单行协议。

## 6. 状态机、终止条件与失败分类

每个 Note ID 必须始终属于且仅属于一个集合：`not_started`（尚未进入外层批）、`pending`（本批未获有效模型输出）、`accepted`（完整有效结果已缓存但未确认写入）、`terminal`（最终写入结果，如 updated/conflict/commit-uncertain/cancelled/not-run）。不能因为一次模型返回格式错误就先把 Note ID 标记为永久失败；只有满足当前批停止或整个任务终止的条件才最终归类。

**唯一运行阶段（必须实现为显式状态）**：`GENERATING -> FINALIZING -> COMMITTING -> SETTLED`；若无需提交，`FINALIZING -> SETTLED`。只有对应 `run_id` 的一个完成事件能把 `GENERATING` 转入 `FINALIZING`，事件优先级为：已观察到的 Cancel/窗口销毁 > worker 返回的终止原因 > 正常完成。worker 完成时只发一个不可变 `BatchRunResult`（按 NoteSnapshot 原序排列的 `accepted` 完整结果、`current_batch_ids`、`current_batch_pending`、`current_batch_requested_ids`、`not_started`、终止类别、最后安全错误码、请求总数、内部重试数、有效数量）。这四组集合必须以冻结的唯一 NoteSnapshot 序列为准：`accepted`、`current_batch_pending`、`not_started` 三者**互斥且并集等于全部所选 Note ID**；`current_batch_ids` 是**已经发起至少一次 Provider 请求的当前活动批**在激活时划定的 ID 集合，`current_batch_requested_ids` 是本外层批至少一次实际发起请求的 ID 集合（可以包含已经 accepted 的 ID），且是 `current_batch_ids` 的子集。`current_batch_pending = current_batch_ids - (accepted ∩ current_batch_ids)`；`not_started` 包含未激活外层批的全部 ID。**批次预选不产生活动批状态**：下一批首次请求开始以前，`current_batch_ids`、`current_batch_pending`、`current_batch_requested_ids` 均为空，预选 ID 仍属 `not_started`；首次请求开始时同时完成集合转移和请求登记。正常全部完成时当前批集合为空、`not_started` 为空；对已经完成的前序批次，所有 ID 均在 `accepted`。每次请求实际开始时记录该次发送的 ID；不从请求总数、accepted 数量或批序号倒推批边界。进度事件只携带 `{run_id, accepted_count, request_count}`，UI 只更新进度，不借进度或逐条信号修改账本。整个响应必须先完成扫描/去重才原子性地更新 pending/accepted；原 `record_worker()` 的“第一次失败即终态”接口不能用于新重试路径。

**冻结完成动作**：主线程按唯一 `BatchRunResult` 和当前取消状态一次性构建账本及提交参数，记录已经进入 `FINALIZING` 的事实；后续晚到 Worker 事件不能再次触发提交，旧 run_id 事件始终丢弃。`SETTLED` 是唯一显示最终弹窗并恢复交互的阶段，每个所选 Note ID 恰好一个最终状态。模型阶段停止时，`current_batch_pending` 中实际已请求的 ID 归 `not-generated`，尚未请求的 ID（包括 `not_started`）归 `not-started`；已 accepted 的记录最终交由提交结果决定。**没有进入下一批、没有发起请求**的 ID 不得由于已计算批次范围而改变分类。若原子性发送与取消发生竞态，以 worker 调用 `provider.generate()` 前登记的 request-start 事实为唯一分界。账本至少区分 `updated`、`conflict`、`cancelled`、`not-generated`（当前批未完成）、`not-started`（后续批未发）、`not-submitted`、`commit-failed-before-start`、`commit-uncertain`、`persisted-undo-uncertain`，以及成功解析但尚未写入的 accepted 中间态（不能计作 updated）。

**三次零进展**只统计实际已发出的调用尝试，并针对当前外层批待完成集；模型响应中至少有一条**新的且完整有效**记录即为有进展。不把未知 ID、重复 ID、此前已经接受的 ID 或部分字段成功计作进展。无进展错误必须留有最后原因与次数，用于最终弹窗。不要重发已 accepted 的 ID。

**用户 Cancel**：及时阻止新的请求；不可保证中断已经发送给服务端的 HTTP 调用，但其响应不得在取消后被接受或写入。保持当前 Advanced 的取消安全语义：用户取消后不启动新的 Anki 写入；尚在内存中 accepted 但未提交的结果视为取消、不会写入。UI 关闭/销毁也必须走同一安全边界，丢弃迟到信号。收到完整响应与取消交错时，worker **在接受任何该响应记录前**检查取消标志；已观察到取消则不接受。`FINALIZING` 在调用 `CollectionOp.run_in_background()` **之前**复查 cancel、窗口存活和 run_id；如任一失败直接 `SETTLED`，不启动提交。若提交已排队或开始，再取消只能通过 CollectionOp 内部现有逐笔记取消门控阻止尚未提交的写入，**必须等待权威提交结果**，不得由 UI 单凭取消事件断言所有笔记未写入。

**服务端明确超限 / 致命错误 / 三次零进展**：worker 的唯一 `BatchRunResult` 携带停止原因和此前全部 accepted，统一进入 `FINALIZING`；若未取消且存在 accepted，启动**至多一次** CollectionOp，完成/失败后才展示终态；不允许因 `terminal_category` 直接丢弃 accepted，也不允许在 `mark_pending()` 时覆盖 accepted。无 accepted 则直接 `SETTLED`。提交启动后的任何异步失败优先保守标记写入可能不确定，不能仅因 failure callback 而显示“零写入”。

## 7. Anki 持久化与 Undo 边界

为保留基线的可审计性，**采用当前 Advanced 的单次最终 CollectionOp 提交**，而不是每次模型响应后写入 Anki。`accepted` 在模型阶段是内存中的已验证结果；“接受”不等于“已经写入”。这是本版明确的产品取舍，避免把单个任务拆成多个无法保证同一 Undo 分组的写入事务。

- 正常全部完成：worker 返回各外层批累计的 accepted，调用一次现有 `commit_validated_results()`。
- 三次零进展、明确上下文超限或其他不可恢复调用错误：已 accepted 的完整项仍进入**同一次**最终安全提交；未 accepted 的 ID 不写入，显示失败/未执行。若 accepted 为空，不启动 CollectionOp。
- 用户取消、窗口销毁：保持现有“不在取消后开始写入”的合同；尚未提交的 accepted 丢弃。若取消发生在 CollectionOp **已经排队或开始**时，等待 CollectionOp 权威结果并依逐笔记 outcome 结算；即使窗口已销毁也不得访问已销毁 QWidget 或发弹窗。**提交生命周期由独立于 TextTab/QWidget 的、保持强引用直到结算的运行协调对象持有**（如应用级 Coordinator），它拥有 run_id、取消标志、原始快照、accepted 和账本，并成为提交成功/失败回调的唯一结果接收者；CollectionOp 使用存活的 Anki 应用级 parent（例如 `mw`），**不得再使用 `CollectionOp(parent=self)` 或由被销毁 TextTab 的绑定方法承接权威回调**。TextTab 只接收在其存活且 run_id 匹配时的展示通知。窗口销毁仅取消 UI 观察，不能销毁已提交/排队任务的 coordinator；任务返回或明确失败后由 coordinator 完成唯一结算、输出无敏感内容的运行统计并释放自身。关闭 Anki 进程造成回调根本未到达的情况不可声称完成或零写入；本版不新增进程重启恢复机制。不能宣称已写入内容回滚。
- 写入前使用原始 NoteSnapshot 逐条重读，检验 Note Type、所有 Source/Destination 原始值等是否变化；冲突只记 `conflict`，**不再调用模型重新生成**。所有目标字段一次性写入笔记；单笔记 `update_note` / Undo 合并不确定时立即停止剩余写入并明确报告。
- 按既有实现使用 Anki `CollectionOp` 与单个自定义 Undo 项；不能在 worker 线程读写 Collection、调用 Qt UI；不能把预检后过期的笔记对象用于写入。
- 状态账本在结束时对选中每条 Note ID 给出互斥结果，区分 validated-but-not-written、updated、conflict、取消、未尝试、零进展停止、Undo/持久化不确定。**CollectionOp 的提交入口取消返回合同**：若在 `commit_validated_results()` 进入写入前发现 `cancel_event.is_set()`，必须得到权威 `cancelled-before-write` 结果（例如受控 `AdvancedCommitResult.fatal_status="cancelled-before-write"`，`outcomes=[]`，`fatal_error` 可为空），明确此操作没有执行任何 `update_note`、没有创建 Undo 项；coordinator 将本次 accepted **全部记为 `cancelled`**。当前 `advanced_ledger.apply_commit_result()` 在空 outcomes、无 fatal_error 时把 validated 误标 `commit-task-failed`，必须增加此明确结果的分支，不能把该路径当普通成功提交，也不能仅凭 UI 关闭推断取消。该结果仅限能证实入口未写入的取消；提交开始后的空 outcomes / 外层失败绝不能套用此分类。

**提交边界必须区分**：(a) `FINALIZING` 已决定不启动/调用失败且可证明未启动，记 `commit-failed-before-start` 或 `cancelled`；(b) `run_in_background()` 已被调用、CollectionOp 可能排队或运行，但只收到 failure callback、无可信逐笔记结果，所有可能被提交的 accepted 记 `commit-uncertain`，不得声称零写入；(c) 收到 `AdvancedCommitResult`，以其每条 outcome、`fatal_status` 为权威，其余原始 pending/not-started 不得误归入已更新。`update_note()` 抛错和 Undo merge 失败沿用现有明确的不确定状态，永不自动二次提交。仅 `updated` 计入成功写入，accepted 数量不等于更新数量。统计要与用户看见的 Anki 实际状态一致，不要统计“LLM 返回 8 条”就显示“写入 8 条”。
- 成功/部分成功结束后 UI 刷新、Provider 保存仅按照现有 Advanced 的成功提交条件执行；错误路径不能意外覆盖用户设置。

## 8. 弹窗、错误提示与统计

**UI 无常驻说明文字**。运行期间继续复用 Advanced 进度窗口，按真正获得有效输出的笔记数更新，而非仅按调用次数更新；不在失败的每一轮弹出阻塞式弹窗。结束时给出概要：总选择数、模型成功解析数、实际写入数、冲突/未完成/未执行数、模型请求数、内部重试数、停止原因。

- 明确的服务端上下文或输出限制错误：终止弹窗仅显示脱敏、截长、受控 `safe_summary`（如有），不显示服务端原始错误体，并附加原句：**“超出模型上下文或输出限制时，请减小 Batch Size。”**
- 三次零进展：`连续三次请求未产生新的有效结果，已停止后续批处理。` 附可用的最后失败原因，不能断言“LLM 一定不可用”。
- 部分记录成功：不弹错误，不推断截断原因；继续重试剩余项。
- 认证、模型配置、Endpoint 或不可恢复网络异常：报告对应真实原因，勿混称为上下文超限。
- 保留请求取消的明确标识；不给取消前已接受但未写入的结果标 `updated`。
- 日志只输出 provider 标识、batch size、调用次数、有效记录数、重试/错误原因码和耗时等必要元数据；不得输出 Note ID 对应的个人内容、完整 Prompt、LLM 回答或 Token。

## 9. 改动位置、禁止范围

实施时必须使 `ainotepro/services/text/_diagnostics.py`、`openai_text.py` 和 `ollama_text.py` 的错误接口可被模拟验证：成功返回字符串不变，失败使用受控结构化异常；所有新 UI/Worker/账本信号使用 §6 的单一结果结构，不得各自推测写入状态。

建议最小变更文件（不是强制引入新 framework）：

- `ainotepro/ui/text_tab.py`：紧凑 QComboBox 模式显示，Advanced worker 分批调度，进度及终止路径；**Easy 的 GenerationWorker 与 OCR 路径不动**。
- `ainotepro/core/advanced_text.py` 或同级纯 Python 模块：多笔记 JSONL 请求构造、逐行解析、身份与结果校验；单笔记 `parse_response` 保留。
- `ainotepro/core/advanced_ledger.py`：将重试中的非终态与终态分开，保持一次运行每个 Note ID 仅一个最终结果。
- `ainotepro/config/manager.py`：`advanced_batch_size` 的默认值、校验与持久化，遵守原有跨域和 CAS 规则。
- `ainotepro/core/advanced_commit.py`：原则上复用当前安全提交协议；确有必要改动时必须有专门回归测试。
- 对 Provider 的 HTTP 异常适配只做必要且不泄露响应内容的可测试分类；不得改变所有 Easy 请求的清洗、模型发现和模型参数行为。
- 后续实现提交再同步 README 中英文、Changelog、AnkiWeb 描述、发布验收文档及版本规划；**当前 SPEC 提交不修改这些文档或版本号**。

## 10. 可执行验收矩阵（开发及第三方审计依据）

| ID | 场景 | 必须验证的结果 |
|---|---|---|
| BAT-01 | Easy 单笔记/多笔记文本与 OCR | 现有 Worker=1、旧 Prompt 和输出/写入规则完全不变 |
| BAT-02 | Easy/Advanced 切换 | 仅一行紧凑 Label+下拉，Advanced 1–20，Easy 保留 Image Recognition 状态 |
| BAT-03 | 新旧配置 | 缺失、非法、越界、布尔值→默认 10；选择可持久化，不覆盖其他域 |
| BAT-04 | B=1 | 调用现有单 JSON 协议；输入、输出、校验语义不变 |
| BAT-05 | B=10、恰好 10 条有效 | 一次 provider.generate；Note ID、字段完全准确 |
| BAT-06 | B=10、8 有效、1 无效、1 缺失 | 第二次仅发送剩余 2 条；成功后下一新批仍为 10 |
| BAT-07 | B=10，8→1→1 有效 | 无进展计数每次清零，无已接受 ID 重发 |
| BAT-08 | 返回截断 JSONL、空行、说明行、乱序 | 独立接收完整有效行，不需要长度/截断识别 |
| BAT-09 | 同一 ID 重复、未知 ID、已接受 ID、非法字段 | 本次相应 ID 不接受，不写错笔记；正确行保留 |
| BAT-10 | JSON 对象重复键、NaN、空字段、嵌套类型、恶意换行/引号输入 | 严格拒绝非法记录；允许 JSON 转义后的 `\n`/`\t` 和多行字段，拒绝未转义控制字符与非法代理 Unicode；输入边界不被注入破坏 |
| BAT-11 | 0、0、0 有效返回 | 第三次后停止**全任务**，不运行后续批；报告未完成 |
| BAT-12 | 0、1、0、0、1 | 每次有进展清零；不因累计失败次数停止 |
| BAT-13 | 明确上下文超限 | 立刻停止；不重试、不截断；弹窗有指定中文提示 |
| BAT-14 | 认证失败/Endpoint 错误/超时 | 准确分类；不得误提示上下文超限或无限重试 |
| BAT-15 | 前面批次成功，当前批三次零进展 | 已接受项安全提交一次，未生成项与后续未执行项不写 |
| BAT-16 | 用户 Cancel、关闭窗口、迟到 worker 信号 | 不再发请求；不在取消后开始提交；没有访问已销毁 Qt 控件 |
| BAT-17 | 生成后 Source/Destination/Note Type 被外部修改 | 快照冲突、跳过写入、不重新请求、不误关联 |
| BAT-18 | Undo 创建/合并失败，update_note 抛异常 | 不确定性分类正确、停止后续写入、不自动重复提交 |
| BAT-19 | 同时有完整成功、冲突、失败、未执行 | 账本每个 ID 一个终态，统计与真实写入一致 |
| BAT-20 | 多字段/中文字段名/HTML/Cloze/Default、自定义 Prompt | 原 Advanced 预检、模板、内容边界和结果语义不变 |
| BAT-21 | Provider 返回空/过长/损坏 JSONL | 有效行可接受、解析受界限保护、状态机有限终止 |
| BAT-22 | B=20、N=21、B>N、N=0 或只有无效源 | 外层分批、尾批、全量预检拒绝边界正确 |
| BAT-23 | 远端提供者和本地 Ollama、llama.cpp、vLLM 等模拟端点 | 共用 generate 协议，原有输出保留、失败可诊断 |
| BAT-24 | 实际 Anki（Windows/Linux 及上位 SPEC 要求的平台） | UI、主线程/CollectionOp、取消/撤销与有效批次运行人工验收；不能以某一平台替代上位平台门槛 |
| BAT-25 | B>1 Prompt 编译与 B=1 兼容 | B>1 不包含单 JSON 后缀；B=1 完整 Prompt 逐字符保持一致 |
| BAT-26 | 重复 ID 与不可识别坏行 | 可完整解析带 ID 的非法字段行污染相同 ID；坏 JSON 不猜测 ID，不影响其他合法 ID |
| BAT-27 | 20 MiB 总量及 1 MiB 单行边界 | `==` 允许，`>` 拒绝；总量超限整响应零进展，单行超限跳过但继续扫描后续行；合法多行字段与非法控制字符边界可复现 |
| BAT-28 | Provider 异常分类矩阵 | 结构化上下文限制、普通 400、401/403、404、429、5xx、超时、Ollama 错误体，分类正确；恶意/敏感原始错误体不进入 UI 或日志，仅受控摘要及指定超限提示 |
| BAT-29 | 非取消故障有 accepted | worker 唯一终态携带 accepted、当前外层批 ID、实际已请求 ID、当前批 pending 和 not_started；N=25/B=10 在第 2 批发送前/发送后终止时分类不同；最终仅启动一个提交 |
| BAT-30 | 取消与提交竞态 | 接收前取消、FINALIZING 门控、已排队提交、进入 commit 前取消空 outcomes（权威 cancelled-before-write）、提交中取消、窗口销毁后权威回调、迟到信号；每个 run_id 结算一次 |
| BAT-31 | 提交失败与 Undo 不确定 | 未启动、已提交但无结果、逐笔记返回三种情况准确，外层 failure 不称零写入 |
| BAT-32 | 配置与 UI 跨窗口交错 | advanced_batch_size 更新不覆盖 Prompt、Provider、Audio；运行时禁用并恢复真实能力状态 |
| BAT-33 | 真实 Anki 单 Undo 验收 | Windows/Linux 等上位平台上的多批次一次 Undo、提交排队/进行中关闭 TextTab 后独立 coordinator 仍结算、无已销毁控件调用；Anki 进程退出不虚报完成 |
| BAT-34 | 真实 Anki Easy/OCR 回归 | 上位平台 Easy 单 worker、原 OCR、Advanced B=1/B>1、Prompt 保存与实际写入结果测试 |

CI 单元测试应尽量使用 Qt-free 的纯函数测试状态机和 JSONL 解析，UI 用已有假控件方式检查路径；模拟 Provider 记录每次请求中的 Note ID，以强制验证 **“10→2→下一批10”**。真实 LLM 的性能测量可以附带，但本 SPEC 不保证固定加速倍数。

## 11. 验收及冻结门槛

第三方审计应一次覆盖：产品合同、自相矛盾之处、实际源码实现可行性、JSONL 身份与解析安全、重试状态机终止性、异常/取消、Anki CollectionOp 与 Undo、配置迁移、Qt 生命周期、测试足够性。不得只检查用户刚提出的一两条，然后下一轮再提出本来可以一并发现的问题。

**仅当审计对整份 SPEC 给出 PASS 或 PASS WITH MINOR（且无阻断项）后，方可冻结 SPEC 并安排代码开发。** 审计发现的同一主题问题应提供一份集中整改表，说明优先级、对应位置、建议合同和验收测试；不要提交代码或擅自更改 main。审计未执行的测试必须写明“未执行”，不能以静态分析声称通过。
