# AINotePro Audio V2 — FAIL 报告集中整改后独立静态复核请求

- **任务类型**：Implementation Remediation Re-Audit（只读、代码差异与冻结 SPEC 覆盖审计）
- **仓库**：`ernestyu/AINotePro`
- **上轮 FAIL 基线**：`22c92cf3c8aad66ee59a2039871285ec9229ba22`
- **本轮整改固定代码提交**：`758c831e04afc5be25d142e6b18592519cd66b69`
- **设计 SPEC**：`docs/specs/audio-v2-kokoro-profiles-implementation-spec.md`，冻结版本 `de4bce6604f47f40fa850b712b9e53868d53bce9`
- **审计范围**：上述两个代码版本之间的差异及受影响的调用链，不重新设计产品、不扩大功能。
- **状态**：**整改代码候选，尚未通过本轮复核，也未在 Anki / Kokoro 实机验证。**

## 一、必须遵守的用户边界

用户明确要求**不运行任何测试，不触发 CI，不构建、不安装或启动 Anki，也不执行 Gradio 端到端请求**。原因是用户将在 Mac mini 上 pull 代码，使用实际 Anki 插件运行环境测试并反馈。

本轮请**只读检查代码与 SPEC**；不得修改仓库、创建或执行测试、触发 GitHub Actions、提交 Commit/PR。所有运行时兼容性结论必须标记为 `NOT VERIFIED — USER FIELD TEST PENDING`。不能以“未执行测试”代替静态缺陷的判断，也不能把代码修订等同于已验收。

## 二、上轮问题逐项复核

| ID | 上轮问题 | 本轮修改位置与审计要点 |
|---|---|---|
| P0-01 | 笔记更新成功但撤销合并失败被误报 `failed_commit`，后续继续提交 | `ui/tts_tab.py::_commit`：笔记更新后重新读取验证；区分已提交、未提交、状态无法确认；撤销合并异常后 `_stop_batch`，但仍尝试来源记录；无可用 undo API 时在写媒体前拒绝。**检查异常分支是否仍可能误分类、是否存在多笔合并其他用户操作的风险。** |
| P1-01 | SSE 固定 120s 导致长合成提前中断，阶段时限缺失 | `services/audio/kokoro_gradio.py`：队列 120s、合成与下载共用 300s、整体 420s，独立后台 SSE reader + deadline supervisor；HTTP、文件校验错误分类。**标准库 HTTP 仍未经真实 Gradio 证据验证，SPEC §13.1 传输门槛仍是发布阻断项。** |
| P1-02 | `save_all` 浅层更新导致 Text 旧快照覆盖新数据 | `config/manager.py`：基于 baseline 的变更叶节点合并、冲突拒绝、Audio 独立整体替换；`ui/text_tab.py`：Prompt 元数据通过 ConfigManager 原子写入。检查删除语义、默认值、并发冲突及未知键保留。 |
| P1-03 | 关闭后 `_closing` 使结果回调直接返回，批次未完成统计/清理 | `ui/tts_tab.py::can_close/_finish/_advance`：有运行任务时请求取消、延迟真正关闭至 in-flight worker 返回，再统计、关闭进度框和对话框。检查重复 Close、Cancel 与 Qt 生命周期。 |
| P1-04 | Preview 定时 120s 删除文件，不关心播放器状态 | `core/audio_preview.py`、`ui/tts_tab.py::_preview/can_close`：Qt Multimedia `EndOfMedia` / error / explicit close 管理临时 MP3；无 Anki media 写入。**Qt Multimedia 在用户 Anki 内是否可导入、能否播放，未验证。** |
| P1-05 | Edge 启用空 Voice 未被拒绝 | `config/audio_profiles.py::validate_audio`：统一拒绝两 Provider `enabled=True` 且空 voice。 |
| P1-06 | Kokoro 不可用启用 Voice 被静默过滤，改变随机权重 | `ui/tts_tab.py::on_generate_tts`：保留所有配置；只要任何启用块不在运行时可用列表，明确阻断整批。Edge 亦要求 voice 列表有效。 |
| P2-01 | 无 Profile 加载时视觉上默认选中第一项 | `ui/tts_tab.py::_refresh_profiles`：明确“Select Profile; click Load”占位项。 |
| P2-02 | 合成错误分类笼统 | `kokoro_gradio.py` 和 `tts_tab.py::_next`：区分 `failed_download`、`failed_validation`、`failed_synthesis`；探测失败单独显示。检查与 SPEC §13.5 结果枚举的一致性。 |
| P2-03 | Edge 默认被认为 Ready | `ui/tts_tab.py::_request_edge_voices/_refresh_availability`：实际获取到 Voice 列表后才 Ready，失败则禁用 Generate/Preview 并显示原因。 |

## 三、额外必须检查的静态风险

1. **Anki 撤销语义**：`add_custom_undo_entry` / `update_note` / `merge_undo_entries` 的实际分组顺序；如果其他用户操作插入或 API 行为不同，是否可能误合并？如不能从代码保证，请明确 P0/P1 与需现场核验的分界。**不得宣布批次单步撤销已通过验收。**
2. **提交不可确定性**：`update_note` 抛错但实际持久化、重新读取失败、merge 失败、来源索引失败四种组合的准确结果、保守停止和再次 Generate 的安全性。
3. **SSE 与超时**：reader 线程与 response.close 资源释放、无 `generating` 事件时的阶段边界、排队超时、总时限、下载内容与两个输出的可访问性、Gradio Dropdown choices 格式。不得把静态代码逻辑当作真实协议证据。
4. **配置并发**：`save_all` 的 baseline/delta 与默认合并、`update_text_fields`、`set_provider_config`、Prompt 写入，是否仍有不同窗口互相覆盖或删除 Profile 复活。
5. **Preview 资源**：Qt Multimedia 的导入策略、平台支持、播放器停止后是否已释放文件句柄、窗口提前关闭、播放器报错、临时文件遗留。
6. **取消与窗口关闭**：UI 主线程不等待 worker、关闭请求只在任务结果已处理后销毁对话框、统计不遗漏、重复 Close 与批次 Undo 状态不失真。
7. **Voice**：运行时列表失效时保留 Profile 原值，生成前不静默删减权重，Edge 语言与男女筛选仍兼容。
8. **回归边界**：Text 功能 API 不变、无新增自动测试/CI/模型服务端修改。

## 四、输出格式

请提供：
- `PASS / PASS WITH REQUIRED CHANGES / FAIL` 的**纯静态代码审计结论**，并明确其不等于发布验收；
- P0/P1/P2 逐项 `CLOSED / PARTIAL / OPEN` 核销表，提供具体代码位置和理由；
- 发现的新问题及最小整改建议；不要扩展 SPEC；
- 必须由用户 Mac mini 实机验证的最小清单（**只写清单，不执行**）。

**本轮不运行测试、不触发 CI，是用户的明确要求。** 本次修订的 Gradio HTTP 协议、Qt Multimedia、Anki 26.05+ undo、媒体同步、单张/10 张/100 张批次均为 `NOT VERIFIED — USER FIELD TEST PENDING`。
