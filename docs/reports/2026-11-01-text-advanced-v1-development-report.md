# Text Advanced V1 开发报告

- 分支：`feat/text-advanced-v1`
- 指定 SPEC 与分支基线：`aa7cc2fd5dd789b90e7a1daa211605e9b59149e0`
- 状态：实施前阻断；未修改产品代码或 SPEC。

## 阻断：SPEC 冻结前置条件

任务说明表示第三轮独立审计已通过并授权实施，同时禁止修改已审计的 SPEC 正文。指定 commit 的 SPEC §12.4 则要求：“只有审计判定 PASS、无阻断或未核销合同问题，才可另行将 SPEC 标记 FROZEN 并启动 Phase 1。”该文件的状态及结尾仍明确标注尚未冻结。因而当前文件状态未满足启动 Phase 1 的明确前置条件；直接实施或自行修改 SPEC 均与任务约束冲突。

建议由有权维护 SPEC 的人员确认并完成独立的冻结标记，再提供冻结后的权威 commit，或明确以何种不修改正文的权威方式满足该前置条件。解决前未启动 Phase 1–4，未运行测试，也未对 Easy、Audio 或 Anki 集成作通过声明。

## 后续授权与当前进度

用户随后明确豁免上述冻结标记前置条件，授权直接实施。此前的冻结标记问题不再是实施阻断。

Phase 1 已完成：独立的 Advanced Prompt 词法/编译、严格 JSON 响应检查、HTML/Cloze 转换、批量预检、配置域 CAS、一次性旧镜像迁移和删除不复活均已实现并有本地单元测试。Text UI 的 Prompt 加载/保存已接入对应模式的 CAS。

Phase 2 已实现：Text 页面保留 Easy 布局并增加 Easy/Advanced 切换、底部单行多选 Source/Destination、互斥禁选、模式独立 Prompt 命名空间、动态 Advanced Default 与草稿保护。Advanced 隐藏并强制绕开 Image Recognition。

Phase 3 已实现代码路径：先以原始字段值建立完整批次快照并执行全量预检；网络线程只接收不可变快照；每个响应按 JSON 合同验证；最后通过 Anki `CollectionOp` 的串行 collection context 重新读取、比较、给同一 note 的全部目标赋值并只调用一次 `update_note()`。取消或窗口销毁会阻止未提交结果；JSON 失败和并发冲突均零写入该笔记。

本地检查：`python3 -m unittest discover -s tests -v`，35 项通过；`python3 -m compileall -q __init__.py ainotepro` 与 `git diff --check` 通过。现有 Easy/Audio 无界面回归测试通过，不能代表实机回归通过。

尚未完成的验收：实际 Anki 26.9.3 中的 Undo 恢复、多目标写入、取消/关闭竞态、Editor/Browser 刷新和真实 Provider 请求；macOS、Windows、Linux 上 1000×700、870×610 与不同 DPI 的 Qt 多选可操作性。因本机系统 Python 不能加载 Anki app runtime，这些项目未声称通过，必须在目标 Anki 运行时由独立验收完成。

## 第一轮全局审计集中整改（2026-11-01）

基线：`feat/text-advanced-v1@ece3486d57dbaed2dad462581f118b59e993cea5`。本节记录集中整改候选；不修改 SPEC，也不表示 Anki 实机验收已经完成。

| 审计项 | 代码级处理 | 本地证据 | 状态 |
|---|---|---|---|
| AUD-ADV-01 / 02 | `core/advanced_commit.py` 在 `CollectionOp` 的串行上下文内最终重读/比对，单 note 一次 `update_note()`；对每次返回的 `OpChanges` 用 protobuf `MergeFrom()` 聚合。 | `AdvancedCommitTests.test_each_note_is_updated_once_and_all_op_changes_are_aggregated` | 代码与 mock 通过；真实 Undo 待验收。 |
| AUD-ADV-01 / 02 | 提交前要求 `add_custom_undo_entry()` 和 `merge_undo_entries()`；缺失、建组失败、合并失败均停止后续提交且不把该 note 计为成功。 | `test_undo_api_absence_has_zero_note_updates`、`test_failed_undo_merge_is_not_reported_as_success_or_continued` | 真实 Anki Undo 恢复待验收。 |
| AUD-ADV-03 | `update_text_fields()` 不再接受两个 Prompt 映射；`save_all()` 若试图更改 Prompt 域会拒绝，唯一写入路径为 `replace_prompts()` 的域 CAS。 | `PromptStoreTests.test_prompt_maps_cannot_bypass_mode_cas` | 代码通过。 |
| AUD-ADV-04 | 动态 Default 的字段/Note Type 刷新、模式或 Prompt 切换及窗口关闭使用 Save As / Discard / Cancel；Discard 后按新选择重生成，Cancel 恢复选择与正文。 | `AdvancedUiStateTests.test_cancelled_dynamic_default_selection_restores_original_selection_and_draft`、`test_discarded_dynamic_default_selection_regenerates_after_selection_changes` | mock 通过；真实 Qt 待验收。 |
| AUD-ADV-05 | 取消、关闭和迟到 worker 结果均在收集与提交前拦截；提交中再次检查取消，进入单 note 提交后只完成当前 note。 | `AdvancedUiStateTests.test_late_result_and_finish_after_cancel_cannot_schedule_commit`、`AdvancedCommitTests.test_cancel_after_non_interruptible_first_submit_skips_later_notes` | mock 通过；真实 Qt/Anki 待验收。 |
| AUD-ADV-06 | `CheckableFieldCombo` 支持连续勾选、Space/Select 键切换、Escape 的正常关闭、12 项可见上限滚动、完整 tooltip 与互斥禁选；更新禁选状态不再重建弹窗模型。 | 代码检查与 Python 编译 | macOS/Windows/Linux UI 待验收。 |
| AUD-ADV-07 / 08 | 预检仍在 Provider 设置保存、Undo 和请求之前；补充了 Prompt CAS 零旁路和 Collection/状态机 mock 行为测试。现有 Easy、OCR、Provider 输出与 Audio 回归均包含在完整 unittest 运行中。 | `python3 -m unittest discover -s tests -v`：43 passed | 本地通过；真实 Anki/UI 待验收。 |

### 本地命令与实际结果

```text
python3 -m unittest discover -s tests -v  # 43 passed
python3 -m compileall -q ainotepro tests  # passed
git diff --check                           # passed
```

本机检测到 Anki 26.09.3，但仓库 Python 运行时未安装 `aqt`/PyQt，不能在此环境加载 Anki 的 collection 与 Qt 运行时。因此 mock 不能替代真正数据库 Undo、Editor 刷新、窗口销毁或跨平台布局验收。

### 必须在目标 Anki 中执行的复现验收

1. 在临时 profile 创建同一 Note Type 的 10 条笔记，字段为 `Text`、`Scenario`、`Translation`、`Note`；`Text`/`Scenario` 填入可读文本，目标字段先填入可识别旧值。
2. Advanced 选择两个 Source 和两个 Destination，使用动态 Default 或等价的严格 Prompt，连接一个只返回完整 JSON 的测试 Provider；确认覆盖预览并 Generate。每条 note 的两个目标必须同时更新，未选字段不变。
3. 在生成完成后立即执行 Anki Undo；每条已成功 note 的两个目标都必须恢复到准确的旧存储值。重复 1、10、100 条批次，并记录 Undo 菜单中的实际分组行为。
4. 使用延迟 Provider：第一条成功后点击 Cancel；确认正在提交的单条最多完成一次，尚未提交和迟到响应均不写入。再次以关闭窗口/Esc/标题栏关闭重复，确认没有已销毁控件回调或后续写入。
5. 让模型返回缺键、额外键、重复键、数组、围栏外说明和空字符串；每种情况均确认该 note 的所有目标零写入。混选 Note Type、任一空/媒体-only Source 与未匹配 Prompt 也必须是零请求、零写入。
6. 在 macOS、Windows、Linux 各自的受支持 Anki/Qt 版本，检查 1000×700 和 870×610、中文长字段名、10+ 选择项和 DPI 缩放：连续鼠标勾选、方向键/Space、Escape、滚动、禁选 tooltip 以及 Generate/Close/Prompt 操作均须可用。

提交本候选前仍需独立第二轮全文代码与 SPEC 一致性复审；该复审必须覆盖上述八项之外的回归，不得仅形式核销。

## 第二轮全局审计集中整改（2026-11-01）

基线：`feat/text-advanced-v1@b5b0bb7b9d75a48c5168d78e335650e4dad7ba0d`。本轮未修改 SPEC、未触碰 main，也未将 mock 行为称为 Anki 实机通过。

| 审计项 | 处理与代码位置 | 测试证据 | 状态 |
|---|---|---|---|
| AUD-R2C-01 | `ainotepro/core/advanced_commit.py` 将 `update_note()` 已返回后 `merge_undo_entries()` 抛错建模为 `persisted-undo-uncertain`：明确数据可能已持久化、未回滚、Undo 状态未知，并停止后续提交。`update_note()` 自身抛错会重读：只在能确认目标没有持久化时标记 `commit-failed` 并隔离继续；否则是 `commit-uncertain` 并停止。 | `AdvancedCommitTests.test_failed_undo_merge_reports_persisted_undo_uncertainty_and_stops`、`test_confirmed_nonpersistent_update_failure_is_isolated_from_later_notes`、`test_persistent_update_error_is_explicitly_uncertain_and_stops` | 代码/mock 通过；真实事务仍是发布阻断。 |
| AUD-R2C-02 | `TextTab._handle_advanced_commit_result()` 和 `_advanced_summary()` 统一显示 updated、provider-failed、json-failed、conflict、cancelled、commit-failed、commit-uncertain、persisted-undo-uncertain、settings-save-failed、ui-refresh-failed。Provider 设置写失败不改变已知 note 提交结果，且仍会完成 UI 收尾。 | `AdvancedUiStateTests.test_provider_config_save_failure_preserves_commit_outcome_and_finishes_ui` | mock 通过。 |
| AUD-R2C-03 | `AdvancedGenerationWorker` 以 run ID 携带 progress/result/finished 信号；`TextTab` 只接受当前 run 且非 cancel/closing 的结果。关闭时取消，收尾幂等，且不再在 closing 中操作 Qt 子控件。 | `AdvancedUiStateTests.test_stale_worker_result_is_ignored_before_it_reaches_commit_queue`、`test_late_result_and_finish_after_cancel_cannot_schedule_commit` | mock 通过；真实 Qt 生命周期待验收。 |
| AUD-R2C-04 | 一个批次只创建一个 custom Undo entry；每个已经确认更新的 note 都尝试合并到该 entry。冲突、取消与已确认未持久化的失败不影响此前已成功条目；任何持久化/Undo 不确定状态都会停止，不声称回滚。 | `test_each_note_is_updated_once_and_all_op_changes_are_aggregated`、`test_cancel_after_non_interruptible_first_submit_skips_later_notes`、上述 Undo 失败注入测试 | 实际 Anki Undo 分组语义待验收。 |
| AUD-ADV-01 | `OpChanges.MergeFrom()` 汇总每次 `update_note()` 与 Undo merge 的变化通知，且每 note 只执行一次目标字段写入。 | `test_each_note_is_updated_once_and_all_op_changes_are_aggregated` | 真实 Undo/数据库待验收。 |
| AUD-ADV-04 | 第一轮动态 Default 的 Save As / Discard / Cancel 及 Note Type 刷新防丢稿代码未回退。 | `AdvancedUiStateTests.test_cancelled_dynamic_default_selection_restores_original_selection_and_draft`、`test_discarded_dynamic_default_selection_regenerates_after_selection_changes` | Qt 实机待验收。 |
| AUD-ADV-05 | 取消临界点、迟到响应、旧 run 回调与关闭窗口均在提交前拒绝；真正已进入单 note 提交的操作只能完成当前 note。 | `test_cancel_after_non_interruptible_first_submit_skips_later_notes`、`test_late_result_and_finish_after_cancel_cannot_schedule_commit`、`test_stale_worker_result_is_ignored_before_it_reaches_commit_queue` | Anki/Qt 实机待验收。 |
| AUD-ADV-06 | 第一轮连续勾选、键盘、tooltip、冲突禁选与滚动实现保留；本轮没有改变组件语义。 | Python 编译、完整单元回归 | macOS/Windows/Linux UI 待验收。 |

### 第二轮本地实际结果

```text
python3 -m unittest discover -s tests -v  # 48 passed
python3 -m compileall -q ainotepro tests  # passed
git diff --check                           # passed
```

Anki 官方文档确认 collection 修改应使用 `CollectionOp`，其负责 Undoable collection operation 与 UI change 通知；本实现仍以该串行边界运行最终检查与提交。当前环境仅能检查安装包版本，不能在仓库 Python 中加载 `aqt`/PyQt 或真实 collection，因此不能证明 `merge_undo_entries()` 在目标 Anki 的失败回滚/分组细节。

### 第二轮必须实机补验（发布阻断）

1. 在 Anki 26.09.3 的临时 profile 中执行 1、10、100 note 的 Advanced 批次；分别引入目标字段覆盖、并发编辑、Cancel 与窗口关闭，记录每条 note 的结果计数和实际字段值。
2. 成功批次、部分成功批次、第一条后 Cancel 与数据库失败后分别执行 Undo/Redo，记录 Undo 菜单显示和每个目标字段的恢复值。特别验证 `add_custom_undo_entry()` 后每次 `update_note()` 与 `merge_undo_entries()` 的真实分组。
3. 在测试副本中使 `merge_undo_entries()` 抛异常；确认已返回成功的 `update_note()` 数据是否保留，并确认界面只报告 `persisted-undo-uncertain`，停止后续 note，不提示已回滚或完全成功。
4. 使用延迟 Provider 和非法 JSON，验证 Provider/JSON 失败计数、迟到响应丢弃、关闭后的无 Qt 回调；然后在 macOS、Windows、Linux 的 1000×700 和 870×610 执行第一轮 UI 清单。

第三轮必须先核销上述待验收的旧问题，再做全文代码与 SPEC 一致性审计；不得只审查本轮改动行。

## 全局审计整体整改（2026-11-01）

基线：`feat/text-advanced-v1@4183751d5fd4a61693c4a2e65badf6082c65a808`。本轮仅修改运行代码、测试和本报告；未修改 SPEC、`main`、发布配置或 Provider/Audio 核心实现。

| 审计项 | 集中处理与位置 | 本地证据 | 结论 |
|---|---|---|---|
| AUD-G01 | `core/advanced_commit.py` 将最终读/比较阶段和已尝试 `update_note()` 的异常严格分开；前者是 `commit-failed`（零提交尝试），后者永远为 `commit-uncertain` 并停止。两次新鲜 collection 读取仅记录独立观察值，绝不把可变 Note 或旧值观察当作未持久化证明。 | `test_final_read_failure_is_a_per_note_failure_with_zero_update_attempts`、`test_zero_target_observation_after_update_error_is_still_terminally_uncertain`、`test_all_target_and_read_failure_observations_are_explicitly_uncertain` | 代码/mock 已修复；真实 Anki 事务仍阻断发布。 |
| AUD-G02 | `advanced_commit.py` 保持每条笔记一次多字段 `update_note()`，并聚合每次 update/Undo 的 `OpChanges`。Undo 合并失败明确为 `persisted-undo-uncertain`：数据可能已持久化、未回滚、后续不提交。 | `test_each_note_is_updated_once_and_all_op_changes_are_aggregated`、`test_failed_undo_merge_reports_persisted_undo_uncertainty_and_stops` | 代码/mock 已修复；真实 Undo 恢复和分组待验收。 |
| AUD-G03 | `advanced_text.reconcile_field_selection()` 与 `TextTab._load_note_fields()` 保留失效 Source/Destination 的语义选择、仅渲染当前可见子集并阻止 Generate；不再静默缩减请求集合。 | `test_note_type_refresh_retains_invalid_selection_for_generate_to_reject` | 代码已修复；Qt 实机待验收。 |
| AUD-G04 | `advanced_text._TextExtractor` 移除 `hidden`、`aria-hidden`、`display:none`、`visibility:hidden/collapse` 以及非可见节点；媒体/脚本内容仍不作为输入。 | `test_html_and_cloze`（新增隐藏节点样例） | 代码已修复。 |
| AUD-G05 | 既有动态 Default 的 Save As/Discard/Cancel 保护继续覆盖字段变更；本轮失效字段状态不会重写自定义 Prompt。 | `test_cancelled_dynamic_default_selection_restores_original_selection_and_draft`、`test_discarded_dynamic_default_selection_regenerates_after_selection_changes` | mock 通过；真实 Qt 待验收。 |
| AUD-G06 | `TextTab` 拒绝重入 Generate，给 CollectionOp 回调绑定 run ID；取消/销毁会设置 closing+cancel，迟到 worker 结果、进度和提交回调均被隔离。 | `test_late_result_and_finish_after_cancel_cannot_schedule_commit`、`test_stale_worker_result_is_ignored_before_it_reaches_commit_queue`、`test_cancel_after_non_interruptible_first_submit_skips_later_notes` | mock 通过；真实 Qt/Anki 待验收。 |
| AUD-G07 | 新增 `core/advanced_ledger.py`，为每个选中 Note ID 建立唯一终态：updated、provider/json failed、conflict、cancelled、commit failed/uncertain、not-submitted 等；Provider 设置保存失败是独立 issue，永不改变已知提交结果或遗留 busy。 | `tests/test_advanced_ledger.py` 三个混合/不确定/取消行为测试；`test_provider_config_save_failure_preserves_commit_outcome_and_finishes_ui` | 代码/mock 已修复。 |
| AUD-G08 | 批次第二条提交异常保留第一条结果、停止第三条；同值更新、部分/全部/零观察、读取失败和 Undo 合并失败均不伪称回滚。 | `test_second_note_update_error_preserves_first_and_does_not_submit_later_notes`、`test_same_value_update_error_is_not_mistaken_for_a_confirmed_no_write`，以及上述故障注入测试 | 代码/mock 已修复；真实 Anki 仍阻断发布。 |
| AUD-G09 | 完整本地回归覆盖 Advanced 解析/预检/Prompt CAS/迁移、Easy Prompt 行为、Provider 输出、Audio Profile；未把源码字符串检查作为唯一证据。 | 下面 56 项完整 unittest 结果 | 本地通过；实机清单待验收。 |

### 前三轮问题最终状态

- AUD-ADV-01/02、AUD-R2C-01/04：本轮进一步收紧为“写入尝试后任何异常均状态不确定”；真实 Anki Undo/事务仍**未核销、发布阻断**。
- AUD-ADV-03：Prompt 映射仍只能经 `replace_prompts()` 的模式 CAS 修改；`update_text_fields()` 与 `save_all()` 不存在旁路；代码层已核销。
- AUD-ADV-04/05/06、AUD-R2C-02/03：代码和 headless mock 已核销；真实 Qt 销毁、最小窗口、三平台交互仍待验收。
- AUD-ADV-07/08：预检零副作用、Provider 设置保存时机、Easy/Audio 的本地回归均通过；真实 Anki/Provider/UI 不因此宣称通过。

### SPEC §0–12 合规矩阵

| SPEC 章节 | 代码依据 | 状态 |
|---|---|---|
| §0–2 | `TextTab` 的 Easy/Advanced 分流、独立选择和 OCR 隐藏 | 代码/本地回归通过；Qt 实机待验收 |
| §3、§12.1 | `ConfigManager.prompt_snapshot/replace_prompts/update_text_fields/save_all` | CAS、迁移、删除不复活 mock 通过 |
| §4、§11.1 | `advanced_text.parse_prompt/validate_prompt/compile_prompt` | 单元测试通过 |
| §5、§11.2 | `preflight_requests/build_snapshot/field_to_text` 在 Provider 前执行 | 单元测试通过；真实 Anki 读取路径待验收 |
| §6、§11.3 | `parse_response` 与 worker 的每 note JSON 验证 | 单元测试通过 |
| §6.3、§11.5–11.6、§12.2 | `advanced_commit.commit_validated_results`、`CollectionOp` 调用点 | mock 通过；Anki 原子性/Undo 必须实机验证 |
| §7–10 | 模块分层、现有 Easy/Audio 回归测试 | 本地通过；不代表发布验收 |
| §11.7 | run ID、cancel、closing、最后提交前取消检查 | headless mock 通过；真实 Qt 待验收 |
| §11.8、§12.3 | HTML 可见文本与递归 Cloze 转换 | 单元测试通过 |
| §11.9 | Default 草稿保护和 Save As/Discard/Cancel | headless mock 通过；Qt 实机待验收 |
| §11.10 | `CheckableFieldCombo` 的连续选择、键盘、tooltip 与滚动实现 | 仍需 macOS/Windows/Linux 实测 |

### 本轮实际命令和结果

```text
python3 -m unittest tests.test_advanced_text tests.test_advanced_commit tests.test_advanced_ledger tests.test_advanced_ui_state  # 27 passed
python3 -m unittest discover -s tests -v                                                         # 56 passed
python3 -m compileall -q ainotepro tests                                                          # passed
git diff --check                                                                                  # passed
python3 -c 'import anki, aqt'                                                                      # ModuleNotFoundError: No module named 'anki'
```

### 仍需独立实机验收（发布阻断）

1. 在目标 Anki 版本的临时 profile 对 1/10/100 笔记批次验证 multi-field `update_note()`、Undo/Redo、`merge_undo_entries()` 的实际分组和异常后数据库状态。
2. 在最终读/写临界点注入并发编辑、取消和窗口销毁；确认当前笔记最多一次完整提交，后续笔记零提交，Editor/Browser 刷新准确。
3. 在 macOS、Windows、Linux 的 1000×700、870×610 及不同 DPI 下验证多选滚动、方向键/Space、Escape、长字段 tooltip、Prompt 操作和 Generate/Close 可达。

本轮变更模块：`ainotepro/core/advanced_commit.py`、`ainotepro/core/advanced_ledger.py`、`ainotepro/core/advanced_text.py`、`ainotepro/ui/text_tab.py`，以及对应 Advanced 单元/行为测试。实施 Commit 由随后交付记录；未合并 `main`。

## 最终集成验收整改（2026-11-01）

基线：`feat/text-advanced-v1@217a082832c96c6d1fba1dba9648c52c0e32fe9a`。本轮再次复核 SPEC §0–12、前序审计记录、TextTab/MainDialog 的关闭链路与全部本地测试；未修改 SPEC、`main`、Provider 核心或 Audio 实现。

| 审计项 | 处理与代码位置 | 可运行证据 | 状态 |
|---|---|---|---|
| AUD-F01 字段状态 | `TextTab` 以独立的 Source/Destination 未解决集合保存失效选择；编辑其他可见字段不会清空它们。失效字段重新可见后，只有用户明确切换该字段才解除阻断；警告逐项标出角色和名称。 | `AdvancedUiStateTests.test_changing_visible_fields_preserves_each_unresolved_source_and_destination`、`test_explicitly_deselecting_a_returned_invalid_field_resolves_only_that_field` | 代码/行为 mock 通过；Qt 实机待验收。 |
| AUD-F02 关闭生命周期 | `AiNoteProConfigDialog._prepare_dialog_close()` 成为 Close、Esc、标题栏的统一门：先 Prompt 草稿确认、Audio 关闭检查、Text 设置保存，最后以 `prepare_close(confirmed=True)` 设置 cancel/closing。保存或任一确认失败时任务不提前标为 closing。 | `tests/test_main_dialog_close.py` 三项行为测试 | 代码/行为 mock 通过；真实 Qt/CollectionOp 待验收。 |
| AUD-F03 Anki 事务/Undo | 保留 `advanced_commit.py` 的保守持久化分类和批次停止规则；本环境仍无 `anki`/`aqt` 可导入运行时，没有用 mock 推断官方 Undo 或数据库事务。 | 既有 `AdvancedCommitTests` 故障注入套件 | **未通过实机验收，发布阻断。** |
| AUD-F04 全局回归 | 重新运行 Advanced 解析、预检、JSON、CAS/迁移、提交总账、Easy Prompt/OCR 相关分流、Provider 输出及 Audio Profile 测试；本轮未改变已符合合同的解析器、Prompt CAS、Audio 或 Provider 代码。 | 完整 unittest 61 项 | 本地通过；Provider/Qt/Anki 实机待验收。 |

### 先前审计项保持状态

- AUD-G01–G09、AUD-ADV-03、AUD-ADV-07/08 仍保持代码级核销；本轮没有放宽 CAS、预检零副作用、JSON 或结果总账合同。
- AUD-ADV-01/02、AUD-R2C-01/04 仍是“代码/模拟已覆盖、真实 Anki Undo/事务未核销”的状态，不能建议发布。
- AUD-ADV-04/05/06、AUD-R2C-02/03 继续由 headless 行为测试覆盖；新增主对话框关闭链路后仍需真实 Qt 和三平台验收。

### 本轮 SPEC §0–12 复核矩阵

| 范围 | 本轮结论 |
|---|---|
| §0–2 | Easy/Advanced 分流、字段互斥与失效字段阻断保持；新增逐字段失效状态行为证据。 |
| §3、§12.1 | 模式隔离、CAS、迁移和删除不复活未改动；既有 PromptStoreTests 继续通过。 |
| §4、§11.1–11.3 | 词法、集合相等、一次替换与严格 JSON 未改动；AdvancedTextTests 继续通过。 |
| §5、§11.2、§11.8、§12.3 | 批量预检、HTML/Cloze、媒体空输入和零写入路径未改动；单元测试继续通过。 |
| §6、§11.5–11.7、§12.2 | 单 note 一次写入、快照冲突、取消、ledger 和关闭链路均有代码/mock 依据；真实 Anki/Qt 仍阻断。 |
| §7–10、§11.9–11.10 | 动态 Default 草稿、主窗口关闭、Easy/Audio 回归维持；三平台尺寸、键盘和真实 Qt 生命周期待验收。 |

### 本轮实际结果与未完成验收

```text
python3 -m unittest tests.test_main_dialog_close tests.test_advanced_ui_state -v  # 11 passed
python3 -m unittest discover -s tests -v                                          # 61 passed
python3 -m compileall -q ainotepro tests                                           # passed
git diff --check                                                                   # passed
python3 -c 'import anki, aqt'                                                      # ModuleNotFoundError: No module named 'anki'
```

未完成且必须在目标 Anki 版本复现：1/10/100 条多字段提交及 Undo/Redo；并发编辑、取消、窗口关闭和 `merge_undo_entries()` 异常的真实数据库状态；CollectionOp 回调与 Editor/Browser 刷新；受支持 macOS、Windows、Linux 在 1000×700、870×610 与不同 DPI 下的多选和窗口关闭操作。任何一项未记录实机结果前，Advanced 发布继续阻断。

## 第五轮全局审计整体整改（2026-11-01）

基线：`feat/text-advanced-v1@4b719c403f23f46fcdcc2d1d47e2018b8bf9c0a0`。本轮完整复核字段选择、Note Type 切换、动态 Default、Prompt 管理和 Generate 预检的调用关系；仅修改 TextTab 的字段状态/同步路径及其行为测试，不改 SPEC、`main`、事务层、Provider 或 Audio。

| 审计项 | 代码处理 | 普通 Python/行为测试 | 状态 |
|---|---|---|---|
| AUD-F5-01 | `TextTab` 新增 Advanced-only 的 `Resolve…` 菜单。每个未解决字段按 `Source`/`Destination` 和真实名称列出；用户可单独移除当前 Note Type 中已不可见的选择。菜单操作仅移除目标字段，保留其他选择/失效字段；Default 脏草稿仍走 Save As/Discard/Cancel。 | `test_resolver_entries_always_show_role_and_each_field`、`test_resolver_menu_action_removes_only_the_chosen_unavailable_field`、`test_resolver_cancel_keeps_dynamic_default_draft_and_all_selections` | 代码/状态行为通过；真实 Qt 菜单交互待用户验收。 |
| AUD-F5-02 | TextTab 保存当前 Note Type ID 和完整字段定义；每次 Advanced Generate 前重新读取第一条选中笔记。变化时先刷新字段行并要求用户检查选择/Prompt，再次点击才预检；刷新或动态 Default Cancel 不丢草稿/语义选择。混合 Note Type 仍由全批 `preflight_requests()` 拒绝。 | `test_note_type_definition_check_detects_browser_selection_change`，既有 `test_batch_preflight_rejects_everything_on_one_invalid_note` | 代码/状态行为通过；真实 Browser 选择变化待用户验收。 |

### 前四轮代码级核销复查

- AUD-G01–G09、AUD-ADV-03、AUD-ADV-07/08：保持核销；本轮没有放宽持久化不确定分类、CAS、预检零副作用、JSON、Prompt 隔离或结果总账。
- AUD-ADV-01/02、AUD-R2C-01/04：仍仅有 mock/故障注入证据，真实 Anki 单次多字段写入、Undo/Redo 和 Undo 合并异常仍是发布阻断。
- AUD-ADV-04/05/06、AUD-R2C-02/03、AUD-F01–F04：动态 Default、关闭门、run ID、取消及迟到结果均保持 headless 行为覆盖；实际 Qt 生命周期与跨平台 UI 未验收。

### SPEC §0–12 代码合规结论

| SPEC 范围 | 代码级结论 | 实机状态 |
|---|---|---|
| §0–2 | Easy/Advanced 隔离、Advanced 无 OCR、真实字段集合、冲突禁选及失效字段显式解除保持。 | Qt 多选待用户验证。 |
| §3、§12.1 | 独立 Prompt 命名空间、CAS、Default、迁移和删除不复活未改动，现有 PromptStoreTests 通过。 | 配置文件实际升级待用户验证。 |
| §4、§11.1–11.3 | 词法、集合相等、一次渲染、严格 JSON 和单 note 响应隔离未改动，AdvancedTextTests 通过。 | Provider 实际响应待用户验证。 |
| §5、§11.2、§11.8、§12.3 | HTML/Cloze、媒体空输入、批量预检零副作用未改动；Note Type 同步在预检前增加刷新门，混类型仍整批拒绝。 | Anki Browser 实际选择待用户验证。 |
| §6、§11.5–11.7、§12.2 | 单 note 多字段写入、保守 Undo/异常分类、取消、关闭、run ID 和 ledger 未改动。 | Anki 事务/Undo/关闭仍未验收、发布阻断。 |
| §7–10、§11.9–11.10 | 本轮只增加紧凑 `Resolve…` 菜单；动态 Default 草稿防丢保持，Easy/Audio 回归通过。 | 870×610、跨平台和 DPI 待用户验证。 |

### 第五轮实际命令与结果

```text
python3 -m unittest tests.test_advanced_ui_state -v  # 11 passed
python3 -m unittest discover -s tests -v             # 65 passed
python3 -m compileall -q ainotepro tests              # passed
git diff --check                                      # passed
```

本轮未尝试真实 Anki/Qt 集成或跨平台测试。用户应在 Anki 中验证：失效字段菜单逐项移除、Browser 选择/Note Type 变化后的“刷新后再次 Generate”流程、混 Note Type 整批拒绝、动态 Default Save As/Discard/Cancel、真实多字段写入/Undo/Redo、取消/关闭以及最小窗口尺寸下的菜单与字段行可操作性。完成前仍不得宣称发布验收通过。
