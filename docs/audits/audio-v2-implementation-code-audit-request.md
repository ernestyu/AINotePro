# AINotePro Audio V2 — 代码实施独立审计请求（不执行测试）

- 任务：**Implementation Code Audit / Read-only / No Tests / No CI**
- 项目：`ernestyu/AINotePro`
- 实施代码固定基线：`main@22c92cf3c8aad66ee59a2039871285ec9229ba22`
- 已通过独立设计审计的 SPEC：`docs/specs/audio-v2-kokoro-profiles-implementation-spec.md`（`de4bce6604f47f40fa850b712b9e53868d53bce9`）
- 音色资料：`docs/reference/kokoro-official-voice-language-catalog.md`
- 交付状态：**代码开发候选，未经过 Anki 实机验收，禁止作为已验证发布版本**。

## 一、用户明确指定的审计边界

**用户明确要求：本轮开发不运行任何测试、不运行或触发 CI，也不要求开发者在自己的环境模拟 Anki 沙箱。** 原因是 Anki 插件必须在用户的实际 Anki Python/Qt/collection 环境中验证；用户将自行 pull 后在 Mac mini 进行真实操作并反馈。

因此，本次第三方审计**只能阅读 GitHub 代码、SPEC 和文档并给出静态代码审计结论**。禁止执行自动化测试、集成测试、Gradio 实测、Anki 启动、部署、构建、GitHub Actions/CI；禁止擅自修改文件、提交 Commit/PR。**不能因为未执行测试而声称已经通过运行时验证；也不要违背用户要求去启动测试。** 对必须实测才能判断的内容标记 `NOT VERIFIED — USER FIELD TEST PENDING`。

## 二、已实施的主要改动

1. `ainotepro/config/audio_profiles.py`：Provider 隔离的三 Voice、可选 en-US/en-GB locale、稳定 Profile ID、结构与业务校验、legacy Edge 迁移。
2. `ainotepro/config/manager.py`：统一配置写入、同目录临时文件和原子替换、旧配置备份、配置修订检测、Audio profiles 整体替换；Text 保存不能覆盖旧 Audio 快照。
3. `ainotepro/services/audio/kokoro_gradio.py`：loopback-only 标准库 HTTP Gradio 探测、队列事件、三输出处理、MP3 数据结构验证。**此方案是待用户实机验证的轻量 HTTP 候选，未满足 SPEC §13.1 对替代传输的真实端到端证据门槛。**
4. `ainotepro/services/provider_factory.py`：注册 Kokoro。
5. `ainotepro/ui/tts_tab.py`：保留 Audio 三 Voice 布局，新增 Profile 工具栏、Kokoro 美/英口音与男女筛选、音色友好标签、离线探测与 Retry、异步合成/Preview、逐笔取消、Skip/Replace、Anki 主线程提交、批次撤销分组接口。
6. `ainotepro/core/audio_provenance.py`：独立原子来源索引、精确声音标签与 SHA-256 所有权校验。
7. `ainotepro/core/manager.py`、`ainotepro/ui/main_dialog.py`：阻断旧的直接音频写入路径，防止绕过新策略。
8. `ainotepro/ainotepro_gui.py`：与现有 Text/Audio 主对话框及关闭/取消状态集成。
9. `README.md`、`changelog.md`：开发候选说明与未测试边界。

**未修改 Kokoro 服务端**，没有引入新 CI 工作流，也没有运行测试。

## 三、请审计的重点

- **P0/P1：静态正确性**。逐文件检查 Python/Qt API 调用方式、可能的启动异常、信号/槽与线程生命周期、UI 构造时机、关闭窗口后回调；指出具体文件/函数/代码证据。不要将“未实测”直接写成“实测失败”。
- **Gradio 协议与依赖**。核对 Gradio 5/6 的 `/gradio_api/info`、`/gradio_api/call/synthesize`、SSE、File URL 和三输出解析是否符合现有 Kokoro `/synthesize`。明确指出与 SPEC §13.1 的偏差：当前采用**尚未实测的标准库 HTTP**，并未使用经过 Anki Python 验证的 `gradio_client`；需要用户现场提供哪些验证证据。不得自行假设已经成功。
- **Profile**。特别检查删除当前 Profile 后不自动加载其他 Profile（要求用户显式 Load），以及 Schema/默认值、迁移幂等、失效 Profile/离线音色恢复、删除不复活、Save/Save As/Load/Delete、切换 Provider 的草稿隔离、配置并发覆盖、Text 保存对 Audio 的影响、源/目标字段缺失行为。
- **三 Voice 与 UI 兼容**。每张笔记均匀抽取完整配置、三个 Preview 独立参数、Kokoro 28 英语音色的美式/英式/男女分组、Edge 原多语言与音量/音调保留、API Key 移除、Provider 探测竞态、未保存配置提示、UI 原位置和滚动。
- **后台/collection/undo**。是否存在 worker 访问 `mw.col` 或 Qt、主线程阻塞、任务完成后回调到已关闭窗口、取消最后门禁、单笔不可中断提交、同一批次单步撤销、编辑器/浏览器刷新。**Anki 26.05+ 的具体 API 语义只能标记待用户实机确认。**
- **媒体与来源**。MP3 验证、Preview 临时文件清理、不写媒体库、默认 Skip、Replace 精确来源验证、字段冲突检测、笔记成功而来源记录失败的 `generated_unmanaged`、已生成与失败统计、跨设备同步、媒体不自动删除、来源索引与 Anki collection 非原子事务。
- **旧入口**。确认 `TTSTab.on_generate_tts()` 是实际对话框入口；`AIManager.generate_audio_for_field()` 和遗留 `MainDialog` 不能继续绕过新安全策略；Text 逻辑不得退化。
- **SPEC 差距**。按 `IMPLEMENTED / PARTIAL / NOT IMPLEMENTED / REQUIRES USER FIELD TEST` 建立需求→文件/函数的逐条映射。尤其识别实现阶段的范围偏差和隐性回归风险。

## 四、审计输出

1. 总体代码静态审计结论：`PASS / PASS WITH REQUIRED CHANGES / FAIL`，**不等于发布验收**。
2. 按 P0/P1/P2 分类的问题，每项给出文件/函数、代码证据、风险、最小修复建议。
3. SPEC 覆盖矩阵；标出静态代码可确认与必须现场测试的差异。
4. 用户 Mac mini / Anki 实测的**最小手动操作清单**，作为用户后续反馈参考；不要实际执行。
5. 明确声明：**用户要求本轮不测试、不运行 CI；第三方审计也不执行任何测试。** 运行时兼容性、Gradio 协议、Anki undo、媒体同步、1/10/100 笔记等均未验证，发布前仍受原 SPEC 门槛约束。

本轮只读审计，不修改代码或配置、不创建测试、不运行测试、不提交 PR、不触发 CI。
