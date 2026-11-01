# AINotePro — Text Advanced 多字段输入与多字段输出实施 SPEC

- **状态：PROPOSED / 待独立第三方审计；不得视为开发授权**
- **日期：2026-11-01**
- **仓库：** \`ernestyu/AINotePro\`
- **冻结代码基线：** \`main@9c5d6284ec39979470369311eab32dfd28911213\`
- **变更性质：** Text 功能增量扩展；本次提交仅新增 SPEC，不修改运行代码
- **版本范围：** Text Advanced V1
- **规范用词：** “必须 / 不得”表示验收硬约束；“建议”非硬约束。具体实现可调整，但不得弱化硬约束。

## 0. 决策摘要与范围

目标是**完整保留现有 Text Easy 行为**，在同一 Text 标签中新增 Advanced。Advanced 在一次生成操作中，读取一条 Anki 笔记**已经存在**的 1 至 N 个文本字段，通过提示词对不同输入字段分别引用，生成 1 至 M 个目标字段；目标字段与全部源字段互斥。Advanced **不允许 OCR、视觉模型请求、音频/视频解析或中间结果自动生成**。当前 Easy 的单源单目标以及现有 Image Recognition 不迁移到 Advanced。

两种模式共用 Prompt Preview、Prompt Name、Search、New、Save、Save As、Delete、Import、Export 控件和模型配置，但 Prompt 列表、内置 Default、最近使用状态和执行协议隔离。保留左侧 Import/Export 和右侧四个 Prompt 操作按钮布局。字段选择仍位于 Text 页面底部同一行，不引入第二套生成页面。

高级模式**输入占位符**使用真实字段名 \`{Text}\`、\`{Scenario}\`；**输出声明**使用 \`{OUT:Translation}\`、\`{OUT:Note}\`。生成前强制校验“勾选集合 = 提示词声明集合”（输入和输出分别独立校验）。验证失败弹出明确错误并在**任何 LLM 请求和任何笔记写入之前拒绝整个生成操作**。多输出由程序要求并解析可验证的结构化响应，再以每笔记一次写入提交。

不包含：将不同笔记中的字段跨笔记关联、链式依赖生成、多轮自动循环、添加/删除 Anki 字段、为不同 Note Type 自动改名映射、让输出字段成为同次生成的输入、Prompt 共享网络服务、重写 Audio。

## 1. 现有代码事实与兼容性基线

以下为本 SPEC 编写时对冻结 Commit 的静态核对；**不是已通过运行测试的结论**。

1. \`ainotepro/ui/text_tab.py\` 的 \`_load_note_fields()\` 从所选第一条笔记的 Note Type 取得字段名，\`source_field_combo\` / \`destination_field_combo\` 均为单选 \`QComboBox\`。
2. \`on_generate_text()\` 有两条路径：Image Recognition 的单条视觉路径，以及纯文本批量路径。后者把 \`(nid, source_text)\` 交给 \`GenerationWorker\`；线程中使用 \`prompt_tpl.replace("{Source Field}", text).replace("{Source}", text)\`，仅返回单字段普通文本。
3. \`_apply_generated_text_result()\` 和视觉路径通过 \`ainotepro/core/utils.py::update_field_content()\` 写入，该函数设置一个字段并立即 \`note.col.update_note(note)\`；**不能直接在多输出循环中调用以实现一次性写入**。
4. 当前 \`_confirm_write_risk()\` 在同源同目标或批量笔记时提示；\`create_undo_checkpoint()\` 是 best-effort 尝试，失败只打印日志。Advanced 需要单独验证实际 Anki 的撤销与提交边界。
5. Easy Prompt 使用 \`text.prompts\` 平面字典与 \`text.last_used_prompt\`；\`_load_prompts()\` 合并内置 Default、遗留 \`user_files/gen_text/prompt.json\` 镜像和用户配置，\`_save_prompts()\` 写配置并尝试写镜像。当前 Default 已受保护且可编辑后 Save As。
6. \`ConfigManager.update_text_fields()\` 当前白名单仅包含 \`prompts\` 和 \`last_used_prompt\`；\`_replace_raw()\` 有原子文件替换和跨域保护，但无专用 Text 域 CAS；\`save_all()\` 等旧入口的影响需要逐一核对。
7. 文本/音频设置与模型 Provider/Reasoning 保存存在于同一用户配置，新增 Advanced 存储不得重置这些配置。

审计人必须对照冻结代码逐项核实；如现状不符，记录事实差异和阻断项，不得以本 SPEC 代替源码事实。

## 2. UI 与模式状态契约

### 2.1 Easy（零行为回归）

Easy 为打开旧安装和迁移后的默认 Text 模式。Source 单选、Destination 单选、\`{Source Field}\` / \`{Source}\` 原有替换语义、Image Recognition、原有 Prompt 名称/内容、Provider 配置、现有生成行为、写入警告和回退体验必须维持。不得强制旧 Easy Prompt 使用 Advanced 占位符或 JSON 输出。对 Easy 的安全修复若不可避免，需单独说明和验证，不得借本任务默改其语义。

### 2.2 Advanced 字段行

在现有底部 Field Mapping 行放置 Easy/Advanced 切换，尽量保持单行高度与现有 Source/Destination/Image Recognition 的紧凑布局。Advanced 的 Source 和 Destination 都通过带勾选项的弹出列表进行多选；列表收起后用可读文本展示选中字段名（多项可省略并通过 tooltip 展示全量）。不得把列表变为常驻多行控件。

- Source 选中数量至少 1；Destination 选中数量至少 1；不设置人为 1:1 限制。
- 同一真实字段不得同时出现在源、目标；UI 中冲突项应禁选或者选择时明确处理冲突，**不得静默替用户改变另一侧选中集合**。建议禁选并标注原因。
- 字段列表只来自当前 Note Type 的**真实字段名**；保留其顺序及大小写。选择集不重复。
- Advanced 禁用/隐藏 Image Recognition，任何隐藏状态也不得影响后端：Generate 强制使用纯文本请求路径；切回 Easy 恢复原先 Image Recognition 的选择状态。
- Easy/Advanced 分别维护本会话中的 Source/Destination 选择；切换模式不应丢失另一模式已选值、无提示覆盖尚未保存 Prompt，也不能自动启动生成。
- 字段勾选变更不能私自修改**已保存自定义** Prompt 文本；不符合选择规则时由生成前校验拒绝。
- UI 须为“无选中笔记”“字段缺失”“多 Note Type 混选”“不支持的媒体输入”提供可理解的错误提示；不得以默认选择第一项掩盖不存在的字段。

### 2.3 Note Type 范围

Anki 的字段属于 Note Type，而不是 Deck。V1 一次批量运行必须选取具有**同一 Note Type 标识和兼容字段定义**的笔记；若混选不同 Note Type，在发出网络请求前**整批拒绝**并报告，不按字段名碰巧相同就混合处理。更换所选笔记时应刷新可选字段，已不存在的字段选择视为失效并阻止 Generate，而非自动重映射。

## 3. Prompt 命名空间、Default 与配置迁移

### 3.1 共用 UI，独立数据

Easy 和 Advanced 共用唯一的 Prompt 编辑器与管理按钮，但 Prompt 列表只显示当前模式的条目。名称在各自模式内唯一（大小写折叠冲突拒绝）；两模式可存在同名自定义 Prompt。

**最小迁移实现建议：** 完整保留 \`text.prompts\` 和 \`text.last_used_prompt\` 作为 Easy 既有存储；独立增加 \`text.advanced_prompts\`（平面名称→正文）、\`text.advanced_last_used_prompt\`、\`text.field_mode\`。避免直接将原 \`text.prompts\` 原地改为嵌套字典，因为这会破坏现有读取、导入导出和旧配置流。实现可以选择其他同等无损方案，但必须先证明兼容性。

- 旧 Easy Prompt、包括历史自定义 Default 内容、顺序、最近使用名称及 \`prompt.json\` 镜像不丢失、不被 Advanced 模式读取成执行模板。
- Advanced 自定义 Prompt 不写进 Easy \`prompt.json\` 镜像；高级模式 Import/Export 要采用显式模式作用域和向后兼容格式，必须防止将 Advanced 文件误导入 Easy。
- 修改 \`ConfigManager.update_text_fields()\` 白名单及必要的加载/保存入口，严格限定只写对应 Text 域字段；不得覆盖其他窗口的 Audio、更不能丢失 Provider API Key 或其他未知配置键。
- 对并发窗口保存同一 Prompt 列表必须提供冲突检测或等效合并保护；不能只因为整文件写入原子就认为不会发生丢失更新。保存失败保留用户草稿，告知错误。
- 明确兼容老用户配置、旧版升级、损坏文件、重复打开、导入/导出、删除、回滚后的安全行为；未知未来字段必须保留。

### 3.2 Advanced Default 是动态示例

Easy Default 保留原有内容与保护规则，**不重置用户曾经自定义的 Easy Default**。

Advanced 有独立的、不可删除和不可直接覆盖的**虚拟 Default**，**不要求在磁盘上按每种字段组合存储**。打开或选择 Advanced Default 时，基于当前 Note Type 和 Source/Destination 勾选自动生成带真实字段占位符的示例：

~~~text
已有输入：
Text: {Text}
Scenario: {Scenario}

生成以下目标：
{OUT:Translation}
请给出自然中文翻译。

{OUT:Note}
简要说明语言学习要点。
~~~

示例只是示意；实际文案必须由**当前勾选集合**动态生成，且每个被勾选字段恰好声明一次。用户可以在预览中临时编辑后 Save As 为自定义 Prompt；不允许把当前草稿保存回虚拟 Default。

当 Default 预览已有用户未保存编辑而字段集合变化、模式变化、切换 Prompt 或 Note Type 时，必须通过确认保留草稿、丢弃或取消切换（例如 Save As / Discard / Cancel，或等效流程），不得不经提示重生成覆盖草稿。自定义 Prompt 不随着字段选择改变而被改写；只在 Generate 时进行严格一致性校验。New、Save、Save As、Delete 的现有易用语义保持，并在 Advanced 名称空间内操作。

## 4. Advanced 提示词语法与严格校验

### 4.1 占位符语义

- **输入引用：** \`{字段名}\`，例如 \`{Text}\`、\`{中文说明}\`、\`{Example Sentence}\`。引用字段名与 Anki 实际字段名严格匹配；不区分真实字段名的假设禁止。
- **输出声明：** \`{OUT:字段名}\`，例如 \`{OUT:Translation}\`。这不是用户输入的替换值，而是明确告诉执行器要生成哪个目标字段。
- Advanced **禁止**把所有源字段合并后放进 \`{Source Field}\`；\`{Source Field}\` / \`{Source}\` 只属于 Easy。Advanced 应把每个独立输入占位符替换成对应源字段的内容。
- 必须以词法解析/一次映射替换实现，不得依次使用 \`str.replace()\` 造成新插入文本中的 \`{...}\` 二次展开。解析在插入笔记内容前完成；用户的字段文本是数据，不能触发占位符解析。
- 允许同一输入字段**重复引用**，但源字段集合按唯一名称计算。目标字段必须恰好**声明一次**：重复 \`{OUT:X}\` 拒绝。
- 当字段名称含空格、中文、冒号、花括号、或以 \`OUT:\` 开头时，解析可能产生歧义。实现前必须制定**无歧义的转义或拒绝策略**：不能悄悄误匹配；字段名若无法安全表达，界面在生成前明确拒绝并说明限制，且不得读取错误字段。不能以正则只支持英文标识符。
- 普通 Prompt 的 JSON 示例、代码片段及其他大括号内容不得因严格校验而无条件误判为字段引用；必须明确占位符词法与非占位符文本的界限。审计须测试此处冲突和转义行为。

### 4.2 生成前集合相等校验（用户确定的硬要求）

记 \`S\` 为 UI 勾选的真实 Source 字段集合，\`D\` 为勾选的真实 Destination 字段集合；\`IS\` 为提示词解析所得**唯一输入引用集合**，\`OD\` 为提示词解析所得**输出声明集合**。在每次点击 Generate 时，必须全部成立：

1. \`|S| >= 1\`、\`|D| >= 1\`、\`S ∩ D = ∅\`。
2. \`IS = S\`，即已勾选输入一个也不能缺，未勾选输入一个也不能多；分别显示缺失与多余名称。
3. \`OD = D\`，已勾选输出一个也不能缺，未勾选输出一个也不能多；输出声明不得重复。
4. 不接受未知字段、非法/有歧义的引用语法、Easy 专用占位符或输入输出角色混淆。
5. 当前笔记选择和 Note Type 全部有效，全部选中笔记都有 \`S ∪ D\` 字段；Prompt 不为空；Provider/模型配置满足原有生成前检查。
6. **检查在任何发送请求、创建写入检查点和修改笔记前完成**。任一失败以清楚列出字段名、缺失/多余类别的警告**拒绝整批生成**，不得降级为 Easy 或偷偷缩减字段集合。
7. Save/Save As 可以保存未匹配当前字段组合的自定义 Prompt 草稿；一致性是**Generate 前检查**，避免用户编辑中被强制改写。

Example：Source 勾选 \`Text, Scenario\` 而 Prompt 只出现 \`{Text}\`，报缺少 \`{Scenario}\`；Destination 勾选 \`Translation, Note\` 而仅有 \`{OUT:Translation}\`，报缺少 \`{OUT:Note}\`；Prompt 引用未勾选的 \`{Extra}\` 同样报错并拒绝。

## 5. 输入来源边界（Advanced 不支持 OCR）

Advanced **只读取每条笔记在运行开始时已持久存在的字段文本**；绝不在本次执行中创建 OCR、图片描述、语音识别等中间内容。用户如需处理 PPT 截图，先通过 Easy 的 Image Recognition 将识别结果写入独立字段，检查后再执行 Advanced。

- 源字段可含普通 Anki HTML 富文本；需要有确定的 HTML→可读文本转换规则，保留必要换行/标点，处理 HTML entity，并防止图片 \`<img>\`、音频 \`[sound:...]\` 等媒体标签被错误当作图像/语音内容；不能下载 URL、读本地媒体文件或提交多模态载荷。
- 如果源字段只有图片、音频或空白而没有可用文本，则该笔记不得发起 Advanced 生成；在本次批次预检阶段汇总报告，**建议整批阻断**以免静默跳过；实现 SPEC 须固定唯一行为并做验收测试。
- 批量任务在 Anki 主线程/受支持的 collection 线程先获取每条笔记必要的纯文本及目标字段值、Note Type、版本/变更证据；工作线程只能使用这个不可变快照。后续输出不回流为本轮其他输入，不跨笔记引用。
- 生成过程应设上限和报错策略（单字段内容过大、批量过大、模型上下文不足）；不得在未经用户确认时静默截断文本。避免在日志中输出完整字段内容或 API Key。
- 包含敏感笔记信息的多字段输入仅发送至界面已选择的 Provider；不得自动发送到其他服务。

## 6. 输出协议、解析和写入事务

### 6.1 插件管理的输出协议

用户在 Prompt 中负责描述 \`{OUT:字段名}\` 应生成的**内容要求**，**不需要手写 JSON**。插件根据 \`D\` 自动附加确定、可测试的输出协议，要求模型返回**单个 JSON 对象**，键为真实目标字段名，值为字符串。例如：

~~~json
{
  "Translation": "可能很难融入进去。",
  "Note": "It might be hard to... 可用于表达预期困难。"
}
~~~

Advanced 无论目标 1 个还是多个，都使用**同一 JSON 协议**，避免单输出纯文本/多输出 JSON 两套行为。单条笔记一次 LLM 请求，不允许自动进行隐式第二轮 LLM 补全、OCR 或依赖链生成。可以添加原生结构化输出参数作为可选能力，但不得假定所有 OpenAI-compatible、Ollama、本地端点都支持同一参数；默认有可跨 Provider 使用的文本输出校验路径。

\`{OUT:...}\` 是受解析器识别的输出声明，不能作为有歧义的原始字面标记直接发送给模型；渲染器应生成明确的输出字段名及其相关指令，并附加统一 JSON 契约。用户填写在声明附近的自然语言说明如何与目标字段一一对应，必须有文档和确定规则。

### 6.2 收到响应后的硬校验

任何字段写入前必须验证：响应是可解析的 JSON 对象，允许的外层包装（如 Markdown code fence）有明确且有限的规则；无重复键、无未知键、键集合**恰好等于** \`D\`；每个值必须是非空字符串；不得将错误文本、拒绝消息或模型未生成结果写入笔记。不能用宽松的正则截取结果或依赖字典遍历顺序分配字段。响应不合格时该笔记所有目标字段**零写入**，显示失败原因，不得部分提交。

### 6.3 目标覆盖与原子性

- 所有目标字段均是用户已明确勾选的已有 Anki 字段。**禁止自动新建字段**，禁止写入输入字段。
- 目标字段已有内容的处理规则必须明确、保守、可见：V1 在生成前对“将覆盖非空目标”的笔记与字段进行批量汇总预览，并要求用户明确确认；用户取消则整批不执行。不得静默追加，也不得因为多个目标同时选择就覆盖未勾选字段。
- 每条笔记完成全部输出校验后，在 Anki 许可的 collection/UI 线程上重新读取该笔记，校验 Note Type 和所有相关 Source/Target 是否与运行快照一致；若被其他操作修改，**该笔记零写入**并报告冲突，不覆盖并发编辑。
- 在**单个 note 对象**上设置全部目标字段，调用**一次** \`update_note\`（或等效的 Anki 官方原子/撤销 API）；不得复用当前每字段一次提交的 \`update_field_content()\` 循环。若底层提交失败，不能报告成功；需通过 Anki 支持的事务机制保证该笔记不存在半更新。每笔记原子，不要求跨整批所有笔记进行全局事务。
- 保留/改进 Anki Undo 可撤销性；必须实测真实 Anki 环境，不得把目前 best-effort \`create_undo_checkpoint()\` 作为事务保证。批次已成功的其他笔记不因某一条失败而被静默回滚。
- 不允许 worker 线程直接读写 \`mw.col\` 或修改 Qt 控件；UI 关闭/取消后不得再写入已经失效的结果。进度、失败、取消、恢复与重复点击 Generate 要有确定状态机。

## 7. 实施范围与建议模块

1. **Text UI：** \`ainotepro/ui/text_tab.py\` 增加模式切换、多选下拉、互斥禁选、模式独立状态、Advanced Prompt 展示与 Generate 分流；不得将复杂校验全部堆入 Qt 回调。
2. **独立纯逻辑模块（建议新增）：** \`ainotepro/core/advanced_text.py\`，负责实际字段名解析、字段集合校验、Prompt 编译/单次替换、HTML 纯文本输入、结构化输出解析与验证。要求无 Anki/Qt 依赖，能单测。
3. **生成编排：** 复用纯文本 Provider/worker 概念但为 Advanced 定义明确的快照/请求/结果数据结构；Easy 的 GenerationWorker 与视觉生成路径可以不动。避免跨线程访问 note 对象。
4. **写入层：** 新增“一次更新多个目标字段”的 Anki 安全提交接口或单独编排；不可逐字段重复调用 \`update_field_content()\`。
5. **配置：** \`ainotepro/config/manager.py\`、必要的 defaults/migration，管理独立 Advanced Prompt 与最近使用/模式状态；保留现有 Easy Prompt 与 Audio 域。
6. **文档与测试：** 更新 README、变更日志、发行检查表；独立覆盖迁移、提示词、字段名、跨平台 Qt 多选组件、生成前预检、结果校验及真实 Anki 事务行为。

**禁止项：** 为 Advanced 启用 Image Recognition、自动 OCR、隐式字段读取、自动生成中间输入、忽略不匹配 Prompt、逐字段独立提交、自动改写已保存用户 Prompt、清空现有 Easy 配置。

## 8. 验收矩阵（必须有可复现证据）

### 8.1 单元与静态检查

- Easy 原路径回归：单选、\`{Source Field}\` / \`{Source}\`、OCR/视觉与非视觉、多 Prompt 操作、原有配置和音频不变。
- Advanced UI：0/1/N Source、0/1/M Destination，Source/Destination 互斥、勾选摘要、切模式恢复、不同 Note Type、隐藏的 OCR 勾选状态不能触发视觉调用。
- 动态 Default：每个选中源/目标各声明一次；勾选增减生成一致；编辑后切换的保存/放弃/取消；Save As 后成为静态自定义 Prompt，不被以后勾选改写；Easy Default 内容不变。
- 提示词：字段名中文/空格/大小写/前后缀相似/冒号/特殊大括号/非法占位符、重复输入引用、重复输出声明、未勾选引用、多勾选未使用字段、未知字段、\`{Source Field}\` 非法、输入文本含 \`{Text}\` 时不递归替换、普通 JSON/代码花括号不误判。
- 批量预检：零笔记、混 Note Type、缺字段、空/媒体-only 输入、过长文本、同源目标、多目标已有内容用户取消；所有这些失败应有**零网络调用和零 Anki 写入**。
- 响应：合格 1 目标及 N 目标 JSON；字段顺序无关；缺字段、多字段、重复键、数组、嵌套对象、空字符串、无效 JSON、额外说明和 code fence 处理、错误/取消/超时、无效 Unicode；异常时零写入。
- 写入：已有非空字段确认、同一 note 一次提交、未选字段不变、冲突与陈旧快照拒绝、线程边界、Undo、失败回滚、多笔记其中一笔失败不影响其他成功笔记。
- 配置：旧安装升级、Easy Default 历史定制保留、删除不复活、两模式同名、导入导出跨模式、两个窗口并发写、异常配置/旧版恢复、音频/Profile 及 Provider 设置不被覆盖。

### 8.2 Anki 实机集成

在实际支持的 Anki/macOS 版本完成：Easy 文本生成与 OCR 回归；Advanced 单入单出、多入单出、多入多出；不同 Note Type 拦截；批量 1/10/100 张；取消、中断、关闭窗口、LLM 非法 JSON、已有目标字段覆盖确认；Anki Undo 与编辑器同步刷新；保存 Prompt 后重启 Anki、切换模式、升级插件；含中文字段名/HTML/媒体-only 的笔记；选定 Provider 无结构化输出专用 API 时仍可用文本协议验证。Windows/Linux 至少有兼容性评估及必要的平台测试记录。

### 8.3 不得通过的条件

任何以下问题均为阻断：Advanced OCR 意外发送；某个勾选字段在 Prompt 中缺失却执行了请求；引用未勾选字段仍被读取；未知/缺失输出被部分写入；同条笔记多次提交导致半成品；覆盖源字段；旧 Easy Prompt 丢失或被重排为不兼容格式；Audio/Profile 配置受损；有未验证的线程/Undo 安全风险仍宣称完成。

## 9. 实施分阶段与审计门槛

- **Phase 0（只读事实确认）：** 对照冻结 Commit 建立代码路径图，标明现有 Easy/Prompt/config/worker/write/Undo 机制，解决第 10 节的审计阻断项。
- **Phase 1（纯逻辑与存储）：** 实现可单测的占位符解析、集合一致性、动态 Default 规则、配置隔离/无损迁移与测试；不接入生成。
- **Phase 2（界面）：** 增加 Advanced 单行字段选择及 Prompt 模式隔离，保持 Easy 回归；增加状态切换保护。
- **Phase 3（生成与写入）：** 接入 Advanced 预检、不可变快照、LLM JSON 输出验证、单笔记多目标原子写入、并发修改防护、撤销与错误处理。
- **Phase 4（验证）：** 单元/静态测试、Anki 实机集成和跨平台评估；所有阻断问题修复后才可发布。

本轮任务**仅提交这份 SPEC**。独立审计前不允许以此为授权启动 Phase 1–4 的代码修改；审计发现合同缺口先集中修订 SPEC。

## 10. 提交给独立第三方审计的重点问题

1. **字段语法：** \`{字段名}\` 与 \`{OUT:字段名}\` 在真实 Anki 字段名含 \`:\`、\`{}\`、\`OUT:\` 等情况下是否无歧义？需冻结具体词法、转义/拒绝合同后才能开发。
2. **Advanced Default：** 动态重生成与临时编辑之间的状态机能否保证不丢草稿？Easy Default 历史修改是否完全保留？
3. **Prompt 存储：** \`text.prompts\` 保持原样、新增高级命名空间与配置写锁/CAS 是否正确？导入导出与旧配置兼容是否有遗漏？两窗口并发是否会丢更新？
4. **Qt 多选：** 当前窗口 1000×700（最小 870×610）条件下，一行 Source/Destination 双多选、Image Recognition Easy-only 与模式开关能否布局稳定？
5. **预检定义：** 输入/输出集合双向相等校验是否具备可执行的唯一词法语义？跨 Note Type 与空字段策略是否应更严格固定？
6. **LLM 结构化输出：** 普通文本 Prompt 如何无歧义转换为目标 JSON 要求？不支持 JSON schema 的模型如何处理？合法响应的完整验证是否明确？
7. **Anki 事务：** 现有 \`update_field_content()\`、best-effort checkpoint 与后台 worker 是否满足多字段写入安全？若不满足，如何以 Anki 官方 API 保证一次笔记提交、Undo 和冲突检测？
8. **HTML/媒体：** 纯文本转换是否正确拒绝仅媒体字段，避免图片、音频未经 OCR 却被当作内容？是否会把 HTML 标签泄露到模型输入？
9. **模式隔离：** Advanced 的所有路径是否物理/逻辑上不可抵达 OCR 代码？Easy 的视觉路径是否不受影响？
10. **测试可证性：** 是否有遗漏的失败场景会让模型调用已经发生、而预检之后才发现 Prompt 错误？是否能给出零网络调用、零写入的测试证据？

### 审计交付要求

第三方应输出：**PASS / CONDITIONAL PASS / FAIL**；按 **BLOCKER / MAJOR / MINOR** 列出问题 ID、对应 SPEC 条款、冻结代码位置、复现路径或反例、具体整改建议，以及对 Easy 回归与跨平台的影响。对第 10 节存在未冻结合同或缺少可执行边界的事项，不得仅以“实现时注意”视为通过；必须反馈需要写进 SPEC 的精确定义。

---

**文档性质：** 设计与验收规范；不是测试已通过声明，也不是可直接上线的实现结果。
