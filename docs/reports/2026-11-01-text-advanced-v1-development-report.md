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
