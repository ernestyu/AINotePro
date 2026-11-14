# AINotePro

[English](README.md) | [简体中文](README.zh-CN.md)

AINotePro 是一款 Anki 插件，可根据笔记字段内容生成 AI 文本或语音，并写入指定字段。可从浏览器（Browse）菜单或笔记编辑器工具栏打开。

**当前源码版本为 1.2.1（候选版本，尚未发布）。** 插件窗口标题从 `manifest.json` 读取版本号，不再硬编码。顶部 `Model` 用于选择大模型，底部 `Mode` 用于选择 Easy 或 Advanced 工作模式。源码合并到 GitHub 不等于 AnkiWeb 已发布新版；真实 Anki/Qt 验收与 AnkiWeb 发布仍是独立步骤。

## 功能

- **Text Easy**：从一个来源字段生成文本，写入一个目标字段；支持已保存的提示词和可选图像识别。Image Recognition 不再受 Provider 名称白名单限制；用户可针对实际支持视觉输入的模型与自定义接口主动勾选。如果模型或接口明确拒绝图像输入，插件弹窗提示并停止后续 OCR 笔记请求；Advanced 仍不支持图像识别。
- **Text Advanced**：支持带复选框的来源/目标字段多选；Batch Size 1–99，多个笔记通过 JSONL 独立验证，生成前对全部选中笔记统一预检。
- 保存、加载和删除提示词，支持受保护的 Default；Import/Export 一次处理 Easy、Advanced 提示词和全部 Audio Profile 的统一 JSON。
- GitHub 手动 Save/Load 可同步完整 Library；通过 HTTPS API 工作，Token 保存在系统凭据库，不需要 Git、gh 或 SSH。
- 13 个内置文本 Provider：OpenAI、Anthropic、DeepSeek、OpenRouter、DashScope/Qwen、Moonshot/Kimi、Zhipu GLM、SiliconFlow、Groq、Gemini、llama.cpp、vLLM 和 Ollama。
- 支持模型列表 Refresh（服务端需提供模型枚举接口）、手动输入模型名称，以及按 Provider 保存模型和配置。
- **Reasoning 对全部 13 个 Provider 开放**，按模型保存 Off、Low、Medium、High 或 Model Default。
- Audio：Edge TTS 和可选本地 Kokoro MLX；Edge 音色列表显示地区代码（如 `US-AriaNeural`、`GB-SoniaNeural`）；四个独立 Voice 区块、Audio Profile、每条笔记随机选择已启用 Voice、异步合成与受控音频写入。
- 浏览器可选择一条或多条笔记处理。Advanced **没有固定的每批 100 条上限**，但仍对全部选中笔记执行预检。

## 环境要求

- 当前版本以 Anki 26.05 或更新版本为目标；不同平台及版本仍应在实机验证。
- 远程 LLM 和 Edge TTS 需要网络连接；部分服务需要自己的 API Key。
- 本地 Ollama、llama.cpp、vLLM 或 NInfer 必须提前独立启动；AINotePro 不负责部署服务。
- OCR 需要实际支持 OpenAI 风格 `image_url` 消息的视觉模型接口。即使模型名称相同，不同服务端入口也可能只提供文本能力。
- OCR 读取 Anki 媒体目录中的图像或 `data:image/...;base64,...`；不自动下载远程图片。远程图片应先加入 Anki 媒体库。

## 安装

**AnkiWeb：** Anki → `Tools > Add-ons > Get Add-ons` → 输入插件代码 → 重启 Anki。正式发布后才会提供 AnkiWeb 代码。

**本地文件：** 下载 `.ankiaddon`，双击安装，或通过 `Tools > Add-ons > Install from file` 安装，然后重启 Anki。

## Text 使用方法

1. 在 Browse 中选中笔记，从 `AINotePro > Add Context to selected Field...` 或编辑器工具栏打开插件。
2. 选择 **Text** 标签。
3. 选择 Provider；根据需要设置云服务的 **Chat Endpoint** 或本地服务的 **Server Address**，输入 API Key 和模型名称。
4. 编辑 Prompt，选择来源和目标字段。Easy 可以使用 `{Source Field}` 或 `{Source}`。
5. 需要时设置 **Temperature** 和 **Reasoning**，点击 **Generate**。

### Advanced 模式

Advanced 支持来自同一 Note Type 的多个来源字段、多个目标字段。Prompt 使用 `{字段名}` 读取来源字段，并使用 `{OUT:字段名}` 定义每个目标字段，例如：

```text
{Text}
{OUT:Translation} Translate naturally.
```

来源/目标选择必须与 Prompt 声明双向一致。**Batch Size** 是底部紧凑的可编辑下拉框，预设选项 1–10，默认 1，可手工输入 1–99（最多两位）。原先显灰的 Resolve 独立按钮已移除，失效字段可在来源/目标字段下拉中取消勾选。选 1 时继续使用原 Advanced 的单笔记 JSON 对象协议；选择 2–99 时，一次请求处理多条笔记，以独立 JSONL 记录按 Note ID 关联结果。若一批 10 条只有 8 条有效，便接收这 8 条，仅重试未完成的 2 条；当前批全部完成后再开启新的 10 条。连续三次没有新有效记录则停止整个任务；服务端明确报告上下文或输出限制时立即停止并提示减小 Batch Size，不自动查询上下文。所有笔记在请求前经过统一预检：字段定义、来源文本是否为空或仅有媒体内容等；任意笔记不合格时整批拒绝。写入非空目标字段前会询问确认。

Advanced 不进行 OCR；Easy 和 Advanced 的提示词分别保存。Prompt 中需要字面花括号时使用 `{{` 和 `}}` 转义。**不存在固定的每批 100 条笔记限制**；Batch Size 只是单次 LLM 请求包含的笔记数量，不限制整个选择集。生成阶段累计已验证结果，正常完成或非取消故障停止时通过一次 Anki CollectionOp 复查并写入，保留 Undo；提交前取消则丢弃尚未写入的结果。Easy 的 1 Worker 和 OCR 不变。

### 提示词管理

在 **Prompt Name** 中选择已保存的提示词即可加载。**New** 新建未保存草稿；**Save** 新建或更新当前提示词；**Save As** 另存新名称；**Delete** 删除选中的已保存提示词。Import/Export 保留。

内置 **Default** 不能直接覆盖、删除或经 Import 覆盖，但可以临时修改并通过 Save As 保存副本。切换有未保存修改的提示词时，会按情况出现 Save / Discard / Cancel。提示词及配置保存在升级时保留的 `user_files` 中。

## Provider、Reasoning 与 Temperature

大多数文本 Provider 使用 OpenAI-compatible Chat Completions 接口。预设仅提供便捷的默认接口和模型，不保证所有模型或账号的 API 能力相同。

**Reasoning：** 所有 13 个 Provider 都可以选择 Off、Low、Medium、High 和 **Model Default**，并分别保存当前模型的选择。

- **Model Default**：不发送覆盖服务器推理设置的字段，由服务器默认行为决定。不同平台兼容性不确定时应使用此选项。
- **Off / Low / Medium / High**：OpenAI-compatible 请求分别发送 `reasoning_effort: none / low / medium / high`。例如通过 DeepSeek 预设连接自定义 NInfer Endpoint 时，Off 会发送 `reasoning_effort: "none"`，以请求关闭 Thinking。服务器是否接受及执行取决于实际接口和模型；不支持的参数可能返回错误。
- **原生 Ollama**：Off 发送 `think: false`；Low、Medium、High 发送 `think: true`，**不保证存在三级强度差异**。
- **Temperature** 位于 API Key 右侧。插件将当前值写入请求，但具体模型是否采用该设置由服务端决定。

**调试日志：** 使用 `AINOTEPRO_DEBUG=1` 或已有 DEBUG 配置，可显示实际发出的 Temperature、Reasoning 参数（或 `server_default`）、最大输出 Token 是否设置、Stream、请求耗时与 API 提供的 Token 用量。不会打印 API Key、完整 Prompt 或完整响应。请求中存在参数不等于服务端保证执行。

**模型列表：** 点击 Refresh 从 Provider 的 Models Endpoint 查询；此界面不提供可编辑的 Models Endpoint 输入框。云端使用已保存或内置的模型列表地址；llama.cpp、vLLM 从当前 Server Address 推导 Chat 和 Models 路由。查询失败时可以手动输入模型名称并点击 Check。

默认服务商示例见 [英文 README 的 Provider 表](README.md#provider-notes)。自建 OpenAI-compatible 服务可通过可编辑的 Chat Endpoint 接入，不需要改变模型文件。

### Text 底部按钮

左侧从左到右为 **Enjoying AINotePro? Star it on GitHub → Restore Default LLM Parameters → Help**；右侧保持 **Close → Generate**。Restore 只恢复当前 Text Provider 的 LLM 参数；**保留 API Key**，本地 Provider 也保留当前服务器地址。Audio 标签不显示 Restore。

Text Easy 和 Audio 会在生成前检查本批选中的所有笔记：必须属于同一个 **Note Type（笔记类型）**，且所选 Source/Destination 字段存在。存在不同笔记类型时会警告并停止整批生成，不调用模型，也不写入笔记。同一笔记类型的不同 Card Template（卡片模板）仍可一起处理；Text Advanced 已有独立整批预检。

## 提示词库导入、导出与 GitHub

**Import / Export** 现在一次处理完整的 AINotePro Library（`format: AINotePro.library`，`version: 1`），单个 UTF-8 JSON 同时保存 Easy、Advanced 提示词和完整 Audio Profiles（Edge/Kokoro、四个 Voice、源/目标字段等）。新功能仅接受该统一格式，不兼容开发阶段未发布的 Prompt-only 格式。不导出未保存的草稿、Text Provider 设置、API Key 或当前机器的 Audio Profile ID。若本地导出文件已存在，自动追加 `(1)`、`(2)`。导入遇到同名不同内容则重命名，内容完全相同则跳过；新的 Audio Profile 分配新 UUID，已有 Profile ID 与当前选中项不变。Easy Default 不被覆盖，Advanced 动态 Default 不导出。全部数据先校验，再一次性写入本地配置。

### GitHub 同步：从零开始配置（推荐 Private 仓库）

此功能将**已保存**的 Easy/Advanced 提示词与 Audio Profiles 同步到 GitHub 仓库中的**一个 JSON 文件**。它不会上传整个 Anki 牌组、笔记、音频文件、LLM 设置或 API Key；也**不会自动同步**。全程在网页和插件中完成，不需要 Git、GitHub CLI、SSH 或终端命令。

**第一步：在 GitHub 创建存放个人 Library 的仓库。**

1. 登录 [GitHub](https://github.com)，点击右上角 **+ → New repository**，或直接打开 [新建仓库](https://github.com/new)。
2. **Owner** 选择自己的 GitHub 账号，**Repository name** 可填 `anki-personal-library`。建议选择 **Private**，因为个人提示词及 Audio Profile 可能包含不适合公开的内容。这里创建的是**新的个人数据仓库**，不是 `ernestyu/AINotePro` 源代码仓库。
3. 勾选 **Add a README file** 以初始化仓库，点击 **Create repository**。记录仓库页面显示的默认分支名，通常是 `main`。使用已有仓库也可以，但需要确保目标分支确实存在。
4. 例如仓库地址是 `https://github.com/yourname/anki-personal-library`；插件中只需要填写 `yourname/anki-personal-library`。无需提前创建 `ainotepro-library.json`，第一次成功 Save 会自动创建它。

**第二步：创建权限最小的 Fine-grained Personal Access Token。**

1. 点击 GitHub 头像 → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**；也可以直接打开 [创建 Token](https://github.com/settings/personal-access-tokens/new)。
2. **Token name** 填 `AINotePro Library Sync`，**Expiration** 选择合适的有效期。Token 到期后要重新生成并在插件中替换。
3. **Resource owner** 选择上一步仓库所属的账号或组织。**Repository access** 选择 **Only select repositories**，在 **Selected repositories** 中只勾选 `anki-personal-library`；不需要授权所有仓库。
4. 展开 **Repository permissions**，找到 **Contents**，设为 **Read and write**。GitHub 自动授予 **Metadata: Read-only** 属于正常情况；无需另开 Administration、Actions 或 Issues 权限。对 Private 仓库进行 Save 和 Load 都应使用此 Token；仅从公开仓库 Load 可以不填写 Token。
5. 点击 **Generate token**，立即复制生成的 Token（通常以 `github_pat_` 开头）。**Token 只在创建时完整显示一次**，不要放进仓库、截图、Issue 或聊天。若 Token 丢失，需要重新生成。组织仓库如果要求管理员批准，请先取得批准。

**第三步：在 AINotePro 中逐项填写设置。**

1. 打开 Anki 中的 AINotePro → **Text** 页面，点击 **Save to GitHub / Load from GitHub** 旁边的 **Settings**，进入 **GitHub AINotePro Library Settings**。
2. 按下面的示例填写（将 `yourname` 换成自己的 GitHub 用户名）：

   | 字段 | 填写示例 | 注意 |
   |---|---|---|
   | **Repository** | `yourname/anki-personal-library` | 仅 `owner/repo`；**不要填 GitHub URL 或 `.git`** |
   | **Branch** | `main` | 以仓库页面**已存在**的真实分支名为准，可能是 `master` |
   | **JSON path** | `ainotepro-library.json` | 仓库内的相对 JSON 路径；也可以填 `anki/ainotepro-library.json`；不是本地文件路径 |
   | **Access token** | 粘贴刚复制的 `github_pat_…` | 只在首次保存或需要替换时输入 |

3. 填写 Repository 后，等状态显示 **Token status: Not saved for this repository**；将 Token 粘贴到 **Access token**，点击 **OK**，再在 **Confirm GitHub Token Storage** 弹窗选择 **Yes**。插件会写入操作系统凭据库并读回验证。出现保存成功提示，只说明**本机保存 Token 成功**，不是 GitHub 上传成功。
4. 下次再打开设置，如果看到 **Token status: Saved in system credential store** 且输入框灰色，是**正常状态**，不必重新填写。更新过期 Token 时点击 **Replace Token**，填入新 Token 后 **OK → Yes**；删除本机 Token 时勾选 **Remove saved token for this repository** 并确认。
5. Token 按 Repository 独立保存在 macOS **Keychain**、Windows **Credential Manager** 或 Linux **Secret Service**（需要可用的 `secret-tool`）中，不写入 `user_config.json` 或导出的 Library。系统凭据库不可用时插件会报错，不会改用明文存储。

**第四步：首次上传（Save to GitHub）。**

1. 先在插件中 **Save** 需要保存的 Text Prompt 和 Audio Profile；**未保存的草稿不会上传**。如果当前草稿有未保存更改，先完成保存或放弃修改。
2. 点击 **Save to GitHub**。第一次成功时，会在指定的 Branch 与 JSON path 下创建文件；以后 Save 会读取远端 Library，再与本地内容进行**非覆盖合并**，无需手动编辑远端 JSON。
3. 等待 **AINotePro library saved to GitHub** 或 **GitHub AINotePro library is already up to date** 提示。随后打开 GitHub 仓库，确认在所选 Branch 的目标位置看到 JSON 文件。这一步才证明数据已上传。

**第五步：在另一台电脑导入（Load from GitHub）。**

1. 在另一台电脑安装 AINotePro，打开同一个 **⚙** 设置窗口，填写**完全相同**的 Repository、Branch 与 JSON path。
2. Private 仓库的 Token 需要在新电脑**另外保存一次**（可使用仍有效、权限正确的同一个 Token）；Token 不随 Library 同步。公开仓库的 Load 可以不填写 Token。
3. 点击 **Load from GitHub**。插件将远端内容**合并进本机**，不会删除现有 Prompt 或 Audio Profile；同名但不同内容会增加编号副本。完成后在 Prompt Name 与 Audio Profiles 中核对。
4. 以后在电脑 A 修改后，先 **Save to GitHub**，在电脑 B 再 **Load from GitHub**；B 也有新数据时同理反向操作。这不是自动双向同步。

**常见故障及解决方法。**

| 错误/现象 | 应该检查什么 |
|---|---|
| `check_repository` / HTTP 404 | Repository 必须是 `owner/repo` 而非 URL；确认仓库存在，Token 的 **Resource owner** 正确，并且 **Only select repositories** 中包含该仓库；组织 Token 可能还需批准 |
| `check_branch` / HTTP 404 | Branch 必须已存在；检查是不是 `main` / `master` 填反 |
| HTTP 401 / 403 | Token 可能过期、撤销或权限不足；确认 **Contents: Read and write**，必要时新建 Token 并点 **Replace Token** |
| `read_file` / HTTP 404 | 如果仓库与分支检查已经通过，**首次 Save 时文件不存在属于正常情况**；Load 则必须先有一次成功的 Save，确认 JSON path 完全一致 |
| `create_or_update_file` / HTTP 409 / 422 | 检查并发修改、目标分支保护、写入权限、目标 JSON path 是否冲突；然后重试 |
| 凭据库错误 | macOS 检查 Keychain、Windows 检查 Credential Manager、Linux 检查 Secret Service 会话和 `secret-tool`；不要把 Token 改存为明文 |
| 同名条目出现 `(1)`、`(2)` | 本地与远端存在同名不同内容的版本；这是非覆盖合并的预期结果 |

**V1 冲突合同：** 同步只保证已保存内容的非覆盖合并及同一编号名称系列的重复导入幂等性，**不要求不同电脑的“名称→内容”映射完全一致**。同名不同内容追加数字后缀；不同名称即使提示词文本相同，也允许作为有意保留的别名。Easy/Advanced Prompt 和 Audio Profile 统一使用 Unicode NFC 规范化及大小写无关名称判断。Audio 导出仅包含 V1 允许的 Profile/Provider/Voice 字段；未知字段（包括可能误存的凭据）不会上传或导出。Text Provider 设置和 API Key 不参与同步。

**GitHub 同步诊断与安全：** 程序会先检查 Token 是否能访问仓库与分支，确认后才将目标文件 404 解释为尚未创建。出错弹窗会显示失败阶段（`check_repository`、`check_branch`、`read_file`、`create_or_update_file`）、HTTP 状态码和 GitHub Request ID。轮转日志位于 `user_files/logs/github_sync.log`，**请求结果也会同步输出到启动 Anki 的终端**；内容包括阶段、HTTP 状态、GitHub Request ID、仓库/分支/路径和是否提供 Token，绝不记录 Token 本身、Authorization 请求头或 Library 内容。若日志文件写入失败，弹窗将明确显示日志写入失败的原因，不再误报日志路径。Keychain 显示已保存 Token 不代表其已获得私有仓库权限；请检查 Fine-grained Token 的 Resource owner、Selected repositories、Contents 权限和有效期。反馈问题时提供错误阶段及脱敏日志即可，不要提供 Token。


## Audio 使用方法

1. 选择 **Audio**，在 **Generate using** 选择 **Edge-TTS** 或 **Kokoro MLX (Local)**。Kokoro 需要自行启动本地 Gradio 服务，默认地址 `http://127.0.0.1:7860`；不可用时使用 Retry。
2. 配置最多四个 Voice 区块。Kokoro 提供美式/英式口音、Female/Male、Voice 和速度（0.70–1.30 倍）；Edge 提供语言、性别筛选及 Speed、Volume 调节；现有音色列表在人名前显示地区代码（如 `US-AriaNeural`、`GB-SoniaNeural`），不增加 Accent 筛选器。界面已移除原有 Pitch 控件。每条笔记从完整启用的 Voice 区块中等概率选择一个。
3. Speed、Volume 滑杆两端用 **Qt 绘制的左/右箭头按钮**调节，每次调整 1%。Kokoro 不支持的 Volume 控件仍保持原有禁用规则。
4. 选择 Source/Destination。默认遇到已有声音标签时跳过；Replace managed audio only 需要匹配本地来源记录及媒体哈希。
5. 选择现有 Audio Profile 即立即加载其设置。有未保存更改时，切换会要求 Save / Discard / Cancel；Save 保存的是此前 Profile。新名称可用 Save 创建，Delete 只删除 Profile，不删除音频文件。Generate 可以使用未保存设置，不会自动保存 Profile。
6. 预览使用 Qt Multimedia 和临时 MP3；语音在后台合成，Anki 媒体注册与集合写入由 UI 线程处理。

Kokoro HTTP 适配器采用标准库请求，等待队列 120 秒、处理与下载 300 秒、总计 420 秒的时间限制。生成后的音频一旦同步到 Anki 媒体库，移动端播放不需要连接原 TTS 服务。

## 隐私

文本生成会向选定的 LLM Endpoint 发送 Prompt 和所选来源字段；OCR 可能将 Anki 媒体图像编码后发送给视觉模型。Audio 会向 Edge TTS 或配置的本地 Kokoro 服务发送所选文本。API Key、模型及相关设置保存在本地 `user_files/user_config.json`。

如笔记包含医疗、法律或其他保密信息，应先了解所用服务的隐私政策。完整说明见 [隐私政策](PRIVACY.md)。

## 故障排查

- 文本没有写入：检查来源字段、Prompt 占位符、目标字段以及模型是否返回有效内容。
- OCR 失败：确认实际 Chat Endpoint 支持视觉输入；远程图片请先添加到 Anki 媒体库。
- Refresh 失败：手动填写模型，并使用 Check 验证连接。
- Reasoning 失败或似乎无效：确认目标模型/API 是否支持传入字段；无须强制控制时选择 Model Default。
- 本地 Provider 失败：确认模型服务器正在运行且 Anki 能访问其地址。
- Audio 未生成：确认 Voice 已启用且来源/目标字段存在。
- 旧版本 Audio 按钮显示为空白：更新到使用 Qt 标准箭头图标的版本并重启 Anki。

## 反馈与开发

问题和功能建议：[GitHub Issues](https://github.com/ernestyu/AINotePro/issues)。报告时提供 Anki 版本、操作系统、Provider、接口地址、模型名和错误信息；**不要提交 API Key**。

代码入口为 `__init__.py`，主窗口 `ainotepro/ainotepro_gui.py`，Text 和 Audio 分别位于 `ainotepro/ui/text_tab.py` 与 `ainotepro/ui/tts_tab.py`。

打包前可运行：

```bash
python3 -m compileall __init__.py ainotepro
```

`.ankiaddon` 压缩包顶层应直接包含 `__init__.py`，不得多包一层 `AINotePro/`；打包步骤见 [英文 README](README.md#development) 和 [发布检查表](docs/RELEASE_CHECKLIST.md)。

## 许可

AINotePro 使用 MIT License。第三方依赖保留各自许可证，参见 `THIRD_PARTY_NOTICES.md`。
