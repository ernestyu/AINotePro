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

本地检查：`python3 -m unittest discover -s tests -v`，34 项通过；`python3 -m compileall -q __init__.py ainotepro` 与 `git diff --check` 通过。现有 Easy/Audio 无界面回归测试通过，不能代表实机回归通过。

尚未完成的验收：实际 Anki 26.9.3 中的 Undo 恢复、多目标写入、取消/关闭竞态、Editor/Browser 刷新和真实 Provider 请求；macOS、Windows、Linux 上 1000×700、870×610 与不同 DPI 的 Qt 多选可操作性。因本机系统 Python 不能加载 Anki app runtime，这些项目未声称通过，必须在目标 Anki 运行时由独立验收完成。
