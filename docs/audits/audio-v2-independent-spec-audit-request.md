# AINotePro Audio V2 — 独立实施 SPEC 审计请求

**任务类型：Implementation SPEC Architecture & Coverage Audit（只读、独立、完整覆盖）**

**项目**：`ernestyu/AINotePro`

**审计对象（固定版本）**：
- SPEC：`docs/specs/audio-v2-kokoro-profiles-implementation-spec.md`
- SPEC 冻结提交：`65ceb4752fee0556b64bd61768e268432465af69`
- SPEC 固定链接：https://github.com/ernestyu/AINotePro/blob/65ceb4752fee0556b64bd61768e268432465af69/docs/specs/audio-v2-kokoro-profiles-implementation-spec.md
- AINotePro 原代码基线：`2f3efa526b5e16f0d8b0eb5443d42f38c91e7e3c`（v1.0.0）
- Kokoro TTS 服务端基线：`ernestyu/kokoro-tts@d3f8333765d4e3432e51a5ead831b80096064a4e`（私有仓库；如无访问权限请明确标注未核验，不得假设）
- 官方音色资料：`docs/reference/kokoro-official-voice-language-catalog.md`（提交 `d84873e186b786fbf857ca6c3cee8541e0775a98`），原作者资料：https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
- 当前阶段：**仅审计，不开发、不改代码、不提交 PR、不部署**。

## 一、背景与真实需求

AINotePro 是 Anki 桌面插件，现有 Audio 标签通过 Edge TTS 将笔记源字段转成 MP3，并写入目标字段 `[sound:...]`，由 Anki 同步媒体到手机。UI 提供三个独立的 Voice 区块。产品设计要求：用户勾选多个区块时，**每张笔记随机选择一个已启用音色及其对应参数**，以减轻长期使用同一音色的听觉疲劳。用户反馈其本地使用时有效；但 GitHub `main` 当前 `tts_tab.py` 实现遇到首个启用区块即 `break`。请区分“用户体验”“仓库实际实现”“应当达到的验收要求”，不要把它们混为一谈。

用户已在 Mac mini M4 上部署独立 Kokoro MLX + Gradio 服务：`127.0.0.1:7860`、`/synthesize`，输入 `text/voice/speed`，返回 MP3 文件。通过 `gradio_client` 已实测真实合成成功（MP3 65,324 bytes）；**未证明任意直接 HTTP POST 与 Gradio 客户端等价**。目标是在 AINotePro 内增加 Kokoro 作为可选 Provider，而不改 Kokoro 服务端、不要求手机连接 Kokoro。

**最新范围决策（SPEC 第 12 节）**：本轮 Kokoro **仅英语**，保留美式和英式；**现有 Audio UI 兼容性是硬约束**，包括 Generate using、Language、三个 Voice、各自 Preview、Gender/Speed、Edge 的 Volume/Pitch、Source/Destination 与底部 Generate。Profile 仅增加紧凑工具栏；Kokoro 各 Voice 独立选择美式/英式与男女声，使用友好音色名+官方等级。Kokoro 不支持的控件禁用而非破坏布局；Provider 切换不能混淆滑块单位、重置未保存配置或静默回退。Edge TTS 原有多语言功能不得削减。请以当前 `tts_tab.py` 和用户提供的界面截图作为对照基线。

新增官方资料核验：Kokoro v1.0 官方为 8 种语言、9 个语言/口音组、54 个音色，官方音色表带部分 Overall Grade。**现有 Mac mini Gradio 只允许 28 个英语音色**；Audio V2 第一阶段要提供友好分组（语言/口音、男女、名称、官方评级），非英语扩展需修改服务端并验证 G2P，作为另行批准的第二阶段，不能误报已支持。

用户明确要求：保留三个 Voice 区块及随机选音；Kokoro 沿用现有界面但换音色库和有效参数；新增可命名/保存/加载/删除的完整 Audio Profile（包括 Provider 与全部三个 Voice 参数）；选择 Kokoro 时先探测服务，离线不得生成，但可保留和加载 Profile；解决同步阻塞、重复音频追加、Preview 污染 Anki 媒体库。

## 二、审计目标

请独立检查上述 SPEC 对当前代码的**正确性、完整性、可实施性、回归风险、验收可测性**，重点审查：

1. **现状真实性**：核查 `tts_tab.py`、`core/manager.py`、`services/audio/edge_tts.py`、`provider_factory.py`、`config/manager.py`、`core/utils.py`、Anki 入口；确认是否有遗漏调用路径，随机音色是否实际存在于固定版本。
2. **Kokoro API 契约**：Gradio 端点、客户端缓存文件、音色发现、队列、超时、异常处理；Anki 内嵌 Python 是否能安全安装/打包 `gradio_client`；轻量 HTTP 是否真的可行；服务探测不能误判其他 Gradio 服务。
3. **三 Voice 随机选择**：按笔记独立均匀抽取、每个区块参数成套使用、Preview 不随机、零启用阻断、测试可确定；Edge/Kokoro 参数差异与 UI 状态切换。
4. **Profile 机制**：持久化结构、旧 Edge 配置迁移、重复迁移幂等、Load/Save/Save As/Delete 与未保存提示、离线 Kokoro Profile、跨笔记类型字段校验、`ConfigManager` 深度合并导致删除复活的风险、配置写入原子性。
5. **线程安全与批量执行**：Anki collection 与媒体操作线程约束、后台网络调用、取消与关闭窗口、进度、失败隔离、撤销记录、部分成功后的数据一致性。
6. **字段/媒体安全**：重复生成的默认跳过与显式替换；如何可靠识别插件拥有的音频；历史未标记音频、跨设备同步、HTML/声音标签清理、同源/目标字段、Preview 临时文件生命周期。
7. **音色与多语言**：核对官方 54 音色元数据、8 种语言/9 个口音组的区分、官方评级的含义；28 个当前可用英语音色的动态探测与 UI 分组；Profile 中语言/性别/voice ID 的恢复；非英语需要服务端与 G2P 变更是否明确排除在第一阶段外。
8. **UI 兼容性与纯英语范围（强制审计）**：逐条检查 SPEC 第 12 节的布局不变项、三 Voice 原位置、每 Voice 口音选择、两 Provider 参数映射、禁用不支持控件、Provider 切换与 Profile 状态隔离、Kokoro 离线状态机、Edge 多语言不退化；检查是否存在相互矛盾条款，并给出 UI 回归测试矩阵。
9. **兼容、隐私、发布**：Edge TTS 与 Text 不退化；本机地址与非预期远程连接限制；音频不误发其他 Provider；新增依赖及许可证；Anki 26.05+ 打包；README/发布清单/回归测试覆盖。

## 三、审计交付格式

请给出：
- **总体结论**：PASS / PASS WITH REQUIRED CHANGES / FAIL；不因方案大体合理而忽略关键缺口。
- **问题表**：按 P0（阻断）、P1（必须修正）、P2（建议）分级，每项标明 SPEC 章节、代码证据路径/行号、影响、最小修正建议。
- **覆盖矩阵**：逐项对应用户需求 → SPEC 条款 → 实现路径 → 可验证测试；明确缺项。
- **决策清单**：仅列真正需要在编码前冻结的技术选择（尤其 Gradio 客户端、Profile 存储、音频 provenance 与 Anki 线程/撤销）。
- **验收建议**：自动化测试、Mac mini Anki 实测、离线/失败/取消、1/10/100 张、手机媒体同步等，说明哪些不能仅靠 mock 证明。
- **最终意见**：SPEC 是否已足以交给开发者直接实施；若否，列出必须补充的精确条款。

**边界**：只读审计，不修改任何文件、配置、分支或服务；不自行扩大到 Text 标签重构或 Kokoro 模型部署。若无法读取私有 Kokoro 仓库或无法运行 Anki，请把相关结论明确标为“待验证”，不能写成已实测。