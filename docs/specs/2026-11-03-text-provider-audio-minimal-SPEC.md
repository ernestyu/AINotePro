# AINotePro — Text Provider 与 Audio UI 最小改动 SPEC

- **状态：DRAFT，供合同审计；尚未授权开发代码**
- **日期：2026-11-03**
- **仓库：** `ernestyu/AINotePro`
- **新开发分支：** `feat/text-provider-audio-minimal-20261103`
- **唯一代码基线：** `5d1ba19f4bcaeff5ea0d4ff24cbeec115fc509cf`
- **范围：** Text 平台预设与多个 Custom Provider；Audio Pitch 控件移除、Speed/Volume UI 调整
- **工程原则：** 尽可能少地修改现有 Anki 插件。优先复用原有 ConfigManager、Provider Factory、Text 生成与 Audio Profile；不为假设的场景增加通用基础设施。

> 本文件**取代**先前的 `2026-11-03-text-provider-v2-audio-controls-SPEC.md`（R1/R2/R3）作为本任务的需求合同。此前 `35a6cd5` 之后的 Provider V2 开发实现不作为代码基线，也不要求向本分支移植。旧分支与提交只保留供查阅。

## 0. 确定的需求与明确不做的事

### 0.1 要完成的功能

1. Text 内置 **13 个常用平台预设**：云端 OpenAI、Anthropic (Claude)、DeepSeek、OpenRouter、DashScope (Qwen)、Moonshot (Kimi)、Zhipu GLM、SiliconFlow、Groq、Google Gemini；本地 llama.cpp、vLLM、Ollama。
2. 用户可以创建、命名、编辑、删除并直接选择**多套独立的 Custom Provider**。各自保存完整 Chat Endpoint、可选完整 Models Endpoint、API Key、Model、Temperature 和已有可兼容的 Reasoning 设置。Custom 仅支持 OpenAI-compatible Chat Completions。
3. 原有 Together、Perplexity、LM Studio、LocalAI 等旧 Provider 的配置**原样保留、仍能选择和使用**，不因为它们不在 13 个常用预设内而丢失。
4. Audio 保留 Edge-TTS 和 Kokoro MLX (Gradio)，移除三个 Voice 区块的 Pitch UI；Speed、Volume 显示带正负号的百分比，并在滑块两边增加每次 ±1% 的按钮。Kokoro 不支持 Volume 的行为保持不变。
5. 不改变 Text Advanced V1 的 Prompt、字段校验、严格 JSON 解析、`preserve_output`、笔记写入和 Undo，也不改变现有 Audio Profile V2 的媒体、随机选择和 Undo 规则。

### 0.2 严格禁止增加的架构

本次**不得**引入：

- `text.provider_v2` 全新配置体系、`legacy_overrides`、Legacy 只读覆盖层、全量历史配置迁移器或两套参数优先级。
- Provider 独立 CAS、跨进程配置文件锁、额外的多窗口合并策略；不得替换原 ConfigManager 的 Prompt/Audio 既有机制。
- DNS 类别检查、固定 IP 连接、自建 HTTP/TLS 客户端、网络风险授权记录、自定义 HTTP 安全代理层；继续使用现有成熟 HTTP 客户端。
- 持久化的 `effective_generation`、配置指纹、全局任务代际、跨窗口任务同步及为这些功能服务的状态表。
- 自定义 TTS、音频重编码、额外的模型协议模板、替换 Advanced 生成引擎或重构 Anki 笔记提交体系。
- 因为理论上的并发或网络风险而扩大功能范围。真实错误应在现有调用路径局部修复。

**删减原则：** 新增代码必须能对应 §0.1 的一个可见功能或必要兼容修复；否则不纳入本次。

## 1. 基线源码事实与修改范围

本 SPEC 基于 `5d1ba19` 的代码，而不是历轮 Provider V2 修补后的代码：

- `ainotepro/ui/text_tab.py`：当前 Text Provider 固定下拉列表、`_service_map()`、`_populate_provider_cfg()`、`_refresh_models()`、`_test_model()`、Easy/Advanced 入口。
- `ainotepro/services/provider_factory.py`：大多数服务复用 `OpenAITextProvider`，Ollama 使用 `OllamaTextProvider`。
- `ainotepro/services/text/openai_text.py`：现有 `_base()` 在旧 Base URL 后拼 `/v1`，再拼 Chat/Models 路径；保留旧逻辑仅供已有配置兼容。扩展现有适配器即可支持显式完整 Endpoint。
- `ainotepro/services/text/ollama_text.py`：保留原生 `/api/chat`、`/api/tags` 和已有图像请求行为。
- `ainotepro/config/manager.py`：旧 Provider 存在 `text.provider` 和 `text.<provider_key>`。优先扩展现有读写方法，避免另起配置管理器。
- `ainotepro/ui/tts_tab.py`：已有三个 Voice 区块与 Speed、Volume、Pitch；改动只涉及控件和相关读写。
- `ainotepro/config/audio_profiles.py`、Edge TTS 适配器：仅为隐藏 Pitch 和缺省值做必要的小范围兼容调整。

推荐只修改以上直接相关模块及相应测试；新增一个很小的常量／预设表模块可以接受，但不得形成新的 Provider 框架。所有无关文件保持原样。

## 2. Text 平台与 Custom 的界面

### 2.1 下拉菜单

- 将 13 个常用预设按 Cloud（10）和 Local（3）分组。
- 旧 Provider（Together、Perplexity、LM Studio、LocalAI，以及仍需兼容的旧标识）显示在 Legacy/Other 分组；它们仍能使用原来的配置，不自动删除或转换。
- 每个 Custom 直接显示自己的名字，例如“家里的 Qwen”“学校服务器”；可以有多个，不能共用一个 Custom 配置槽。
- 原有已选 Provider 如果仍存在，升级后保持选择，不自动切换 OpenAI。
- 下拉框使用稳定的内部 key／Custom ID 识别选项，**不存在的身份必须明确提示**，禁止默认回退到 OpenAI。

### 2.2 Custom 基本操作

- 支持 New、Save/Edit、Rename、Delete、Cancel。每个 Custom 有不可变内部 ID（UUID 或等价随机唯一 ID）；名称可修改，修改名字不影响配置信息。
- 不允许空名称或忽略大小写后的重复名称。删除前确认；删除当前 Custom 后要求重新选择 Provider，不悄悄发起请求或改用其他 Key。
- 切换选项时，沿用现有 Text 配置保存习惯：成功保存当前配置再加载下一项；保存失败必须保留当前输入并显示错误。
- Custom 字段：`name`、`chat_endpoint`（完整 URL，必填）、`models_endpoint`（完整 URL，可空）、`api_key`（可空）、`model`（可手工输入）、`temperature`、`reasoning_by_model`（仅适用时）。
- 内置官方 Endpoint 可以查看，但不得随意编辑；本地预设的 Server Address 可以编辑。Custom 的两个 Endpoint 可以直接编辑。

### 2.3 Endpoint 与基本调用规则

- **Custom：** 所填 Chat Endpoint 必须原样成为 POST 目标；不自动追加 `/v1` 或 `/chat/completions`。Models Endpoint 为空则禁用 Refresh，但允许手工输入模型并生成；填写后，Refresh 仅请求该完整地址。
- **云端常用预设：** 代码中定义经核实的完整 Chat Endpoint 和（若确有兼容列表接口）Models Endpoint。没有可信 Models 接口的预设禁用 Refresh；不能凭猜测拼 URL。每个预设的 URL／认证格式需在开发时对照服务官方文档验证。
- **本地 llama.cpp、vLLM：** 用户配置 `http(s)://host:port` Server Address；预设按既有 OpenAI-compatible 协议使用 `/v1/chat/completions` 和（支持时）`/v1/models`。无需自建网络客户端。
- **本地 Ollama：** 继续使用已有原生 `/api/chat`、`/api/tags`；不可仅为统一外观而切换到其他协议。
- **旧 Provider：** 如果旧对象只有 `base_url`，**继续采用基线版本的旧 URL 计算行为**，不在升级时重写其 URL 或 Key。要使用新官方预设地址，应由用户明确选择／重置该预设的地址配置；不能因默认表变更静默替换用户原有路由。新安装默认配置可直接使用官方完整 Endpoint。实现需区分“旧文件中显式存在的 base_url”和“程序补齐的默认值”，不能让默认配置合并无意改变旧行为。
- 请求仍采用现有 `requests` 等 HTTP 客户端及其正常 TLS 证书验证；允许用户明确配置自己的本地 HTTP 服务。不新增 IP 固定、DNS 检查、风险确认流程。**不得在日志输出 API Key**。
- Endpoint 只做必要的输入检查（例如 http/https、host、非空 Chat URL），错误清晰提示；请求超时、连接失败和协议不兼容明确报告，不重试到另一个 Provider。
- 对 OpenAI-compatible 的 Chat 请求保持现有 `messages`、`model`、`temperature`、`stream=false` 等结构。Reasoning 仅在后端已知支持时发送相应参数；没有选择时保留原有默认行为。
- 只有已经确认支持兼容图像消息的预设才能提供 Image Recognition；Custom 默认不承诺 Vision。保留旧 Ollama 的已有图像路径，不重写 OCR 功能。

### 2.4 Model、Check 与 Generate

- Refresh 成功后更新模型候选，但保留用户原先手工输入的 Model；刷新失败不擦掉 Model。接口未提供时提示手动输入。
- Check 使用当前选择的 Provider 和当前表单内容，不因先前选择缓存而使用错误的 URL／Key。
- Easy 和 Advanced 在每次开始生成时获取**一次普通配置副本**，供当前批次使用；不需要持久代际或指纹。
- 生成期间遵循原有 UI 取消流程。取消后即使已发送的网络调用稍后返回，**已有取消标记仍阻止其结果再写入笔记**。如果在任务运行时不允许改 Provider/Model，可暂时禁用相关控件直到任务结束或取消，这比增加跨窗口配置状态系统更简单。
- 保留原有 Advanced 的整批预检、JSON 严格输出、`preserve_output=True`、按笔记写入及 Undo；不得让新 Provider 路由改变这些规则。
- 不要求为 Check/Refresh/Generate 新建统一异步框架。现有后台任务继续复用；若旧 Check/Refresh 同步网络调用阻塞 UI，只在相关按钮调用处做必要的局部异步处理，禁止扩展成全局任务系统。

## 3. 旧配置保留与简化存储

### 3.1 旧配置不迁移、不增加覆盖层

**原始数据仍然是唯一真实配置。**

- 保留用户原有的 `text.provider` 和 `text.<old_key>`，包括 API Key、Base URL、Model、Temperature、Reasoning 和未知字段。
- **升级安装不得自动重写、删除或转换**任何旧 Provider 对象，也不创建 `legacy_overrides`。旧 Provider 继续从 `text.<old_key>` 读取；用户主动编辑旧 Provider 时仍直接写回同一个对象。
- 现有 Text Prompt、Advanced Prompt、Audio Profile、媒体及 Undo 数据完全不参与本轮 Provider 迁移。
- 首次启动不需要为旧数据另建迁移备份层；现有保存机制按原样工作。发布前可建议用户自行备份 Anki Profile，但插件不增加专门的数据迁移引擎。

### 3.2 最小新存储

沿用 `user_files/user_config.json` 与现有 `ConfigManager`。只增加真正需要的新内容，例如：

```json
{
  "text": {
    "provider": "custom:9be94ad9-20e5-4a35-b2b9-d3c87a99a5ac",
    "custom_providers": {
      "9be94ad9-20e5-4a35-b2b9-d3c87a99a5ac": {
        "name": "家里的 Qwen",
        "chat_endpoint": "http://127.0.0.1:8080/v1/chat/completions",
        "models_endpoint": "",
        "api_key": "",
        "model": "qwen",
        "temperature": 0.7
      }
    }
  }
}
```

这是**示意性新增字段**，旧 `text.openai`、`text.together` 等对象仍原样存在；实现时不得替换整个 Text 配置结构。存储 UUID 的格式可按当前项目风格细化，但必须能稳定引用 Custom。

- 通过原有 `ConfigManager` 的单次普通保存更新当前选项／目标 Custom，不新增 Provider CAS、跨进程文件锁或新 Schema Version。
- 现有 Prompt CAS、Audio Profile CAS 是旧功能，继续保留，不因为本轮“简化”而删除。
- 配置保存不得误改非目标 Provider、Prompt 或 Audio；处理失败时不覆盖整个配置文件。
- **性能要求：** 切换 Provider 只是加载小型配置；不可每次请求扫描／迁移所有旧 Provider，不引入额外 DNS 查询、网络探测或全局配置锁链。

## 4. Audio UI 最小改动

### 4.1 Pitch

- 三个 Voice 区块移除 Pitch 滑块及标题；不显示 Pitch 控件。
- 历史 Audio Profile 的 Pitch 字段原样保留；用户改 Speed/Volume 或保存 Profile 时不得顺带删除、归零或更改存储的 Pitch。
- 运行时 Edge-TTS 的 Preview 和 Generate 传给现有适配器的 Pitch 均为 **0**。对缺少 Pitch 的旧 Profile 也按运行时 0 处理。仅在执行时生成临时参数副本，**不改写保存的 Profile**。
- 不改 Audio Profile `schema_version=2`。验证逻辑仅放宽“Pitch 可以缺失”，有历史 Pitch 时仍按原范围验证。Edge 生成方法只需小范围兼容处理，不改 TTS 服务实现。

### 4.2 Speed 与 Volume

- 三个 Voice 区块的 Speed 滑块左右各有 `−`／`+` 按钮，紧邻滑块显示 `+0%`、`−10%` 等；每次按钮改变显示值 **1 个百分点**。
- Edge 的 Speed、Volume 均为原有整数 `[-50,+50]`；Volume 也显示同样格式的百分比及 ±1% 按钮。
- Kokoro Speed 底层保存倍速浮点数 `[0.70,1.30]`，UI 显示对应的 `[-30%,+30%]`；滑块与按钮改变的是百分点，执行时按 `1 + p/100` 转换为倍速。
- Kokoro Volume 保持禁用，并明确显示“不支持”；不额外合成音频增益。
- 到达上／下边界时禁用越界方向按钮；滑块、按钮、标签保持同步。

### 4.3 Kokoro 历史浮点值不变

- 旧 Profile 中例如 `speed=1.005`，进入界面后只做百分比显示，**只要用户未操作该 Voice 的 Speed，保存其他参数不能将原值改成 1.00 或 1.01**。
- 只有用户真实操作了该 Voice 的 Speed，才按显示百分点更新速度；对每个 Voice 独立记录是否改动，不需要新的 Profile Schema。
- 对 `0.995`、`1.005`、`0.705`、`1.295` 和临近上下限的值，保证显示不越界、没有操作时保存完全不变、按钮操作后合法。
- 保留 Preview、后台合成、媒体写入、Audio 随机 Voice 选择、Undo 及现有 Kokoro Gradio 接口和 loopback 限制；不扩大修改范围。

## 5. 不变量与必要验收

以下是本次开发必须证明的行为，不要求额外的框架重构。

| 领域 | 必须满足的行为 | 建议的最小验证 |
| --- | --- | --- |
| 内置 13 个预设 | 能从 UI 选取；各自正确指向已验证协议／完整 Endpoint | 预设映射与请求构造单测 |
| 旧 Provider | Together 等能继续使用旧配置；升级不改变旧原始键值及 URL 路由 | 旧 JSON 加载、保存前后比较 |
| Custom 多实例 | 创建两套不同配置，切换不串 Key/Model，改名不丢配置，删除需确认 | ConfigManager 纯 Python 单测 |
| Custom URL | 完整 Chat 不自动拼路径；Models 为空可手动 Model；失败不清空 Model | Mock HTTP |
| 本地预设 | llama.cpp、vLLM 用正确的兼容路径；Ollama 保持原生路径 | Factory／Mock 请求 |
| Check 与 Refresh | 使用当前表单；错误提示可理解；必要时不阻塞 UI | Stub／Mock |
| Easy／Advanced | 取消后不再写入新结果；Advanced JSON、`preserve_output`、Undo 不回归 | 现有离线测试及少量针对性测试 |
| Audio Pitch | UI 不显示；历史字段不变；生成时为 0 | Profile、适配器单测 |
| Audio Speed／Volume | 范围、±1%、边界、标签同步 | 数值逻辑单测 |
| Kokoro 精度 | 浮点历史值未操作保存不变，实际调整后数值合法 | 参数化数值测试 |

**测试职责：** Codex 仅执行必要的 Python 语法／单元／Mock 测试和已有可运行回归测试；**不得启动 Anki、安装插件、改用户 Profile 或宣称已通过 Anki 实机测试**。Anki 的 UI、TTS Preview、制卡生成、媒体与 Undo 由用户最后验证。

## 6. 开发、审计及交付规则

1. **先确认基线。** 本任务只能从 `5d1ba19f4bcaeff5ea0d4ff24cbeec115fc509cf` 加上本份 SPEC 的新分支开始开发。不得在 `feat/text-advanced-v1` 的历次 Provider V2 修补上继续叠加，也不得 cherry-pick 那些架构改造。
2. **以最小差异实现。** 先复用已有代码，只新增直接必要的预设、Custom 管理、Endpoint 分发和 Audio 控件。对每个新增辅助文件解释为何现有文件不能承担其职责。
3. **检查真实调用方。** UI、Provider Factory、Check/Refresh、Easy/Advanced、旧 Provider 和 Audio Preview/Generate 均须全局核对；不得只实现新 UI 而遗漏运行路径。
4. **审计不扩张范围。** 全局代码审计以本 SPEC 的功能、不变量和基线为准；不因假设的多进程竞争、DNS 重绑定或 A→B→A 跨窗口操作重新增加架构要求。
5. **集中修补反馈。** Codex 实现完毕并推送后，ChatGPT 做完整只读代码审计；报告按共同根因整理，区分确定缺陷、待实机验证和非本次范围问题。不要逐轮追加孤立小修。
6. **Git 交付。** 推送到 `feat/text-provider-audio-minimal-20261103`，报告 Commit SHA、文件列表、测试命令和实际 PASS/FAIL/SKIP；不合并 main。
7. **流程固定：** Codex 开发并 Push → ChatGPT 全局只读审计 → Codex 集中修补（如需要）→ 用户 Anki 实机验收。

## 7. 最小实现检查清单（供 Codex 自检）

- [ ] 13 个内置预设和旧 Provider 分组均可选，既有选择不被重置。
- [ ] 多个 Custom 的 URL、Key、Model 互不混淆，保存／改名／删除行为正确。
- [ ] 旧 `text.<key>` 不自动迁移、不删除、不出现覆盖层，旧请求路由保持兼容。
- [ ] 不生成 `provider_v2`、`legacy_overrides`、`effective_generation`、跨进程锁或自建 HTTP 客户端。
- [ ] 仅使用已有 HTTP 客户端请求正确地址，失败不自动换 Provider；不打印 API Key。
- [ ] Check、Refresh、Easy、Advanced 和原有 OCR 路径一致使用正确 Provider。
- [ ] 生成取消后不继续写笔记，保留已有 Advanced 严格 JSON 和 Undo。
- [ ] Audio 三 Voice 不显示 Pitch，保存原 Pitch，执行 Pitch=0。
- [ ] Edge Speed/Volume 和 Kokoro Speed 的百分比、±1%、边界正确。
- [ ] Kokoro 未操作 Speed 时，历史浮点值不变；Audio 其他既有功能不变。
- [ ] 只做离线必要测试，不做 Anki 实机测试，完成后 Push 并提交实际证据。
