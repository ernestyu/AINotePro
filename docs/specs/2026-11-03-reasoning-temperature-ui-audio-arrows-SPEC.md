# AINotePro — Reasoning、Temperature 与 UI 小修 SPEC

日期：2026-11-03
状态：开发合同；最小范围
固定代码基线：`f0220f8b15077401c9722ef69b7d9496fed70633`
分支：`feat/reasoning-ui-diagnostics-20261103`

## 0. 目标与限制

只完成四项：**Reasoning 对全部 13 个内置 Provider 可选并按实际服务端能力发送；终端打印实际 Temperature / Reasoning；调整 Text 标签及底部按钮；修复 Audio 调节按钮图标不可见。**

沿用现有 `TextTab`、Provider 适配器、`ConfigManager` 和 `TTSTab`；不新建 Provider 架构、能力检测服务、HTTP 客户端、额外请求、配置迁移系统。不修改 Advanced JSON 合同、Prompt、Undo、OCR、Audio Profile、语音参数取值或现有保存路径。仅作必要修复。

## 1. Reasoning：所有平台的 UI 均开放

1. 不再使用 `REASONING_EFFORT_PROVIDERS` 白名单来禁用控件或一概丢弃用户选择。13 个 Cloud/Local 预设的 Reasoning 下拉框均可操作：`Off / Low / Medium / High / Model Default`。切换模型和 Provider 后，保留原有按 Provider、Model 存储的选择机制。
2. `Model Default` 表示**不发送任何推理覆盖参数**，由服务端决定；不能解释为 `Off`。`Off` 则必须尝试明确关闭 Thinking，不得静默当成默认值。
3. 请求采用**所连接服务实际支持的协议**，而不是把 Provider 名称当作模型能力认证：
   - **NInfer OpenAI-compatible Chat**：`Off → reasoning_effort:"none"`，`Low/Medium/High → "low"/"medium"/"high"`。即使用户选的是 DeepSeek 预设，只要 Chat Endpoint 指向 NInfer，此控制也必须可用。正常 OpenAI-compatible 自建服务同样允许明确传该参数；服务端若不支持，报告原有请求失败，不静默删除参数重试。
   - **现有官方 Cloud Endpoint**：在当前适配器中仅使用已核实的该 API 参数形态；例如当前 DeepSeek 官方 Chat 可用 `reasoning_effort`，但关闭模式应使用官方接受的 `reasoning_effort:"none"` 或 `thinking:{"type":"disabled"}`，不可用不兼容的别名；其他官方平台按各自当前文档实际支持的参数决定，并允许 Model Default 不覆盖。不能假称所有模型均可执行四档强度；若服务端明确拒绝某档，显示失败原因（不暴露密钥），**不默默当作生效**。
   - **Ollama 原生**：使用该服务支持的 `think` 选项，`Off` 请求关闭；对 Low/Medium/High 若仅支持启用而不支持精确强度，应明确告知当前协议不保证三级区分，不得把开关伪称为强度控制。
4. 不加入新 UI 开关、动态模型扫描、复杂平台能力表。不以“某平台理论上可能不支持”为理由再将控件置灰。请求失败按现有错误流程处理，不额外调用模型。
5. 用户当前实际场景必须覆盖：`Provider=DeepSeek`、`Model=qwen3.8-27b-ninfer`、自定义 `http://<NInfer-host>:8099/v1/chat/completions`，选择 Off 后，实际 POST JSON 包含 `reasoning_effort:"none"`；Model Default 不包含该字段。

## 2. Temperature 与最小诊断

1. 把 Text 页 `Temp:` 标签改成完整 `Temperature:`，位置仍在 API Key 右侧，布局容纳完整文字，不截断或挤压输入框。现有 Temperature 值、范围、保存及请求参数逻辑不变。
2. 沿用已有 `debug_logging` / `AINOTEPRO_DEBUG=1`。DEBUG 的请求开始记录实际**发送**的 `temperature`、Reasoning 参数（参数名与值或 `server_default`）、`max_tokens`（未传显示 `server_default`）以及 `stream`。必须从最终 HTTP body 读取这些值，不能仅打印 UI 选择；兼容 Check、Easy、Advanced、OCR，以及原生 Ollama。
3. 不打印 API Key、Authorization、Prompt、笔记内容、完整响应或带密钥的 URL；沿用已有日志脱敏。不添加流式模式、额外探测、重试或服务端性能推断。Temperature 已发送不等于服务端必然使用，日志只承诺记录真实请求。

## 3. 底部按钮位置和文案

主窗口最底部严格形成两组，位置保持稳定：

左侧：`Enjoying AINotePro? Star it on GitHub` → `Restore Default LLM Parameters` → `Help`。

右侧：`Close` → `Generate`（保留原来靠右的位置）。

只调整排版和 Restore 按钮文案。全部按钮的原有点击逻辑、当前 Provider 的恢复范围、生成中的禁用、Audio 标签隐藏 Restore、Close/Generate/Help 功能**不变**。不得额外弹确认框，也不得恢复全部 Provider。

## 4. Audio Speed / Volume 箭头可见

当前 `TTSTab` 已有 3 个 Voice × 2 个参数 × 两端 `QPushButton("−")`/`QPushButton("+")`；截图表明 macOS 下按钮可见但文本不可见。

只替换其**视觉呈现**，优先使用当前 Qt 能稳定显示的左右方向箭头图标或符号，并保证三个 Voice 的 Speed 和 Volume 左右端都有清晰的 **左箭头（减少）／右箭头（增加）**。保留现有按钮大小附近的布局、信号连接、每次 ±1%、滑杆边界、状态保存和 Kokoro 不支持 Volume 时的既有禁用规则。不改音频生成或 Profile 数据。

## 5. 验收与交付

- 全部 13 个 Provider 的 Reasoning 下拉框可点；按模型切换后保存选择；Model Default 不额外发送推理覆盖；NInfer 经 DeepSeek 自定义地址可发送 `reasoning_effort:"none"`，关闭服务端默认 Thinking。
- DEBUG 日志显示 POST body 实际 Temperature、Reasoning 和 `max_tokens` 是否设置；与 HTTP Mock 捕获参数一致，敏感信息不出现。
- Text 标签完整为 Temperature；底部两组按钮顺序正确，Restore 远离 Close/Generate，功能不变。
- macOS Audio 三个 Voice 的 Speed / Volume 前后箭头可见，左右各调整 1%；不改现有声音/Profile 功能。
- 开发组先全局检查相关调用链再一次性修补，提交单个集中结果或最少的合理提交。只运行离线 Python 语法、必要 Mock/单测、UI Stub；不得在沙箱启动 Anki、访问真实用户 Profile 或修改笔记。用户自行实机验收。
- 汇报最终 Commit SHA、修改文件、测试命令与真实 PASS/FAIL/SKIP。对不支持的服务端参数如实报告，不增加系统性补丁或过度防御性设计。
