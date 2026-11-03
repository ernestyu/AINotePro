# 更新日志

[English](changelog.md) | [简体中文](changelog.zh-CN.md)

本文件是 `changelog.md` 的中文版本；历史条目记录的是当时的实现，当前行为以最新条目为准。

## Text/Audio — Reasoning、日志、界面及批次限制修正（2026-11-03；开发分支）

- 全部 **13 个 Text Provider** 均开放 Reasoning：Off、Low、Medium、High、Model Default。设置按模型保存。Model Default 不发送推理覆盖参数；明确选择时，OpenAI-compatible 请求发送 `reasoning_effort` = `none/low/medium/high`，是否执行取决于实际服务端和模型。原生 Ollama 的 Off 发送 `think: false`，Low/Medium/High 发送 `think: true`，不声称具有三级独立推理强度。
- DEBUG 现在记录实际发出的 Temperature、Reasoning 控制字段或服务端默认值、最大输出 Token 是否设置，以及 Stream。继续记录请求耗时及可用 Token 用量，不输出 Prompt、完整响应或凭据。
- Text 的 Temp 改为完整 **Temperature**。底部左侧依次为 GitHub 链接、**Restore Default LLM Parameters**、Help；右侧保持 Close、Generate。Restore 只针对当前 Text Provider，保留 API Key 及本地服务器地址。
- 删除旧 Legacy/Custom Text Provider 的 UI 和遗留配置，保留 13 个内置 Provider、Chat/Models 独立内部路由；兼容仅保存旧 `base_url` 的云端模型查询；本地 llama.cpp/vLLM 从当前服务器地址推导接口。
- 移除 Advanced **每批最多 100 条笔记**的固定上限；所有选中笔记仍须在请求前通过统一预检，取消、写入及一致性检查保持不变。
- Audio 的 Speed/Volume 增减按钮不再依赖 `−/+` 或 `◀/▶` 文本，改用 **Qt 标准左右箭头图标**；继续每次调整 1%，不更改 Profile 行为。
- 更新离线/Mock 回归测试。**源码修改并不代表 macOS/Anki 实机或真实模型接口已通过验收**，尤其需实测箭头显示与 Reasoning 效果。

## Text — 明确的提示词操作及受保护的 Default（2026-10-30）

- Text 提示词操作变为右侧 New、Save、Save As、Delete。New 创建带名称的空白草稿；Save 更新当前保存的提示词或创建命名草稿；Save As 始终要求使用新名称。
- 禁止经 UI 保存、删除或导入覆盖内置 Default；保留现有用户自定义 Default 内容。切换有未保存修改的提示词时提供 Save / Discard / Cancel；对受保护的 Default 提供 Discard / Cancel。
- 删除无用的 Online 提示词按钮及过时说明；Import、Export 保留。

## Audio — 选择 Profile 后立即加载（2026-10-30）

- 选择已保存的 Audio Profile 后立即加载全部设置，与 Text 提示词行为一致。删除多余的 Load 按钮；仅输入名称不会加载 Profile。
- 离开有未保存修改的 Profile 时提供 Save / Discard / Cancel。Save 保存**此前的 Profile ID**，绝不错误写入将要选中的 Profile；Cancel 恢复原选择和草稿。
- 应用目标 UI 设置前持久化 `last_profile_id`。如并发 Audio 写入阻止切换，则保留旧草稿、恢复原选择。手动 Save 和未保存直接 Generate 的行为不变。

## Text — 按模型保存 Reasoning 及模型选择（2026-10-29）

- 在 Model 旁新增 Reasoning：Off、Low、Medium、High、Model Default。按当前 Text Provider 的各模型分别保存；历史模型默认使用 Model Default。
- **历史实现：** 当时只有指定 OpenAI-compatible Provider 会发送 `reasoning_effort`；High 曾映射为 `xhigh`，原生 Ollama 尚未启用。**2026-11-03 的新实现已替代这些限制。**
- 修复 DeepSeek 等 Provider 重启后模型选择回退：此前 Refresh 先保存旧模型，导致之后选定的新模型未保持。现在用户选择、手动输入、切换 Provider、保存 Prompt、Check、Generate 及 Close/Esc/标题栏关闭均能持久化选择。
- Prompt Save 继续保存提示词，同时提交可见 Provider/Model 设置；不影响 Audio Profile 和已有 Text Prompt。
- 当时仅做静态审查，没有执行真实 Anki 或在线推理测试。

## Audio V2 — 切换标签及重新打开时保留当前 Profile（2026-10-29）

- 修复启动次序问题：来源/目标字段初始化触发信号，在加载保存的 Profile 前就把空 URL、Voice 和未初始化的速度滑杆写入内存草稿，产生错误的“未保存修改”提示、Kokoro 验证失败或速度重置至 0.70 倍。
- UI 初始化期间暂停草稿采集，完整加载最近保存的 Profile 后再接收编辑。
- 无已选 `last_profile_id` 时，优先显示已有的保存 Profile，不强制展示无关的默认草稿。
- 保留准确的已保存 Gradio URL（除首尾空格），包括有效的末尾斜杠，且加载时不错误标记为已修改。
- 新 Kokoro Profile 的三条 Voice 默认速度为 1.00 倍；已保存的速度（包括 0.70 倍）不覆盖。
- 未执行真实 Anki 或 CI 测试；仍需在 Mac 上验证标签切换、关闭重开及各 Voice 速度。

## Audio V2 — Profile Save/Load 字段修正（2026-10-29）

- Audio Profile 的乐观并发检查只覆盖 Audio JSON，而非整个共享配置；Text UI/Prompt 修改不再导致 Audio Save/Load 冲突。
- 一起读取 Audio 快照和版本标记，在另一个 Audio 窗口确实修改 Profile 时继续阻止冲突写入。
- 在 Voice 发现离线或笔记字段暂不可用时保留已有 Voice ID 和 Source/Destination，避免虚假的未保存提示及配置丢失。
- Kokoro Retry 检查当前输入 URL；只移除根路径尾斜杠，并坚持本地回环地址要求。
- 按当时要求未执行测试或 CI；Save/Load 及 Gradio 连接仍需 Anki 实机验收。

## Audio V2 — 紧凑 Profile UI 候选版本（2026-10-29）

- 删除 Audio 标签内层滚动区域，收紧三个 Voice 区块、页边距和主窗口间距。
- Profile 管理区移至 Source/Destination 下方、主窗口按钮上方。
- Profile 选择器改为可编辑保存名称列表；Save 根据名称创建/更新 Profile，历史版本仍需显式 Load。删除 Save As 和 New。**随后 2026-10-30 改为选择后立即加载。**
- Generate 支持直接使用有效但未保存的设置；保留 Audio V2 Profile 存储、Voice 及 Anki 媒体写入规则。
- 按当时要求未执行测试或 CI，仍需实机检查。

## Audio V2 — 静态审计修订候选版（2026-10-29）

- 修复 P0-01：分离笔记持久化验证、Undo 合并与来源记录结果；Undo 失败时停止批次，不把已持久化笔记错误视作未提交；明确记录无法确定的提交状态。
- 修复 P1-01：分别设置队列 120 秒、处理+下载 300 秒、总计 420 秒的 Gradio 截止时间，并分类下载及验证错误。真实 Gradio 协议仍未验证。
- 修复 P1-02：Text 设置按修改字段保存，提供冲突检测；Prompt 元数据通过共享配置管理器原子写入。
- 修复 P1-03：任务 Worker 完成前不关闭对话框；完成后汇总统计并清理。
- 修复 P1-04：Qt Multimedia 根据完成/错误事件与 Close 管理预览 MP3，而不依赖固定 120 秒定时器。运行环境兼容性待验证。
- 修复 P1-05/P1-06：拒绝已启用但未选择 Edge Voice，任何已启用的 Kokoro Voice 不可用时拒绝整批任务，不静默改变随机选择权重。
- 修复 P2-01/02/03：明确“尚未加载 Profile”选择器状态、传输错误分类及 Edge Voice 列表健康检测。
- 当时没有执行测试或 CI；仍需独立只读静态复审和 Mac mini Anki 实机验证。

## Audio V2 — 开发候选版（2026-10-29，尚未经发布验收）

- 新增仅支持英文的本地 Kokoro Gradio Provider，并展示美式/英式、Female/Male 标签及官方 Voice 质量数据。
- 新增具迁移能力、独立 Provider 配置和原子文件替换的版本化 Audio Profile。
- 保留三个 Voice 区块，按笔记从所有启用的完整 Voice 区块随机选择，支持各区块 Preview。
- 音频合成在 Qt UI 线程之外执行，加入取消入口、Anki 媒体来源记录及保守的 Skip/Replace 规则。
- 禁用旧音频直接写入入口，防止绕过 V2 的安全写入路径。
- 当时未运行测试或 CI；Anki/Gradio 运行兼容性及发布验收仍待完成。

## 1.0.0 — 首次 AnkiWeb 发布候选版

- 支持为选中的 Anki 笔记生成文本，并提供多种 OpenAI-compatible Provider 预设（其中部分旧预设已在 2026-11-03 删除）。
- 支持提示词保存、选择后自动加载、删除、导入与导出。
- 保存最后成功使用的模型；支持视觉模型的图像来源模式。
- 支持 Edge TTS 音频生成，并在 Anki 字段插入 `[sound:...]`。
- 配置与提示词保存在升级时可保留的 `user_files` 文件夹。
- 默认不记录完整 Prompt 和响应，以保护隐私；失败时不把 `[Error]` 写入笔记。
- OCR 默认只允许读取 Anki 媒体目录；多笔记或同字段写入前确认并生成 Undo 检查点。
- 修复编辑器工具栏启动及单条笔记在 Anki 主线程应用结果的问题；修复从编辑器启动时的音频字段写入。
