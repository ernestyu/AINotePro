# Kokoro-82M 音色与语言官方资料对照（Audio V2 设计依据）

状态：REFERENCE / 非运行时音色列表。日期：2026-10-29。

## 官方资料

- 模型作者官方音色目录：https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
- 模型卡：https://huggingface.co/hexgrad/Kokoro-82M
- Mac MLX 推理实现：https://github.com/elsakane2015/kokoro-mlx/blob/main/README.md

Kokoro v1.0：**54 个音色，8 种语言、9 个语言/口音分组**。前缀第一字母标识语言/口音，第二字母 f/m 标识女/男。质量等级（Overall Grade）是官方对训练数据质量/数量的综合估计，**不是独立的用户试听评分，也不代表某种年龄、语气、情绪或声音人格**。没有官方等级的音色标为“未评级”，绝不能自行推断。语言覆盖不等于成熟度；官方明确警告非英语 G2P 与训练数据可能不足，短句（尤其少于 10–20 tokens）可能有弱点。

## 54 音色对照表

| 分组 | 女声（音色 ID：官方综合等级） | 男声（音色 ID：官方综合等级） |
|---|---|---|
| 美式英语（a） | af_heart A；af_bella A-；af_nicole B-；af_aoede C+；af_kore C+；af_sarah C+；af_alloy C；af_nova C；af_sky C-；af_jessica D；af_river D | am_fenrir C+；am_michael C+；am_puck C+；am_echo D；am_eric D；am_liam D；am_onyx D；am_santa D-；am_adam F+ |
| 英式英语（b） | bf_emma B-；bf_isabella C；bf_alice D；bf_lily D | bm_fable C；bm_george C；bm_lewis D+；bm_daniel D |
| 日语（j） | jf_alpha C+；jf_gongitsune C；jf_tebukuro C；jf_nezumi C- | jm_kumo C- |
| 普通话（z） | zf_xiaobei D；zf_xiaoni D；zf_xiaoxiao D；zf_xiaoyi D | zm_yunjian D；zm_yunxi D；zm_yunxia D；zm_yunyang D |
| 西班牙语（e） | ef_dora 未评级 | em_alex 未评级；em_santa 未评级 |
| 法语（f） | ff_siwis B- | 无 |
| 印地语（h） | hf_alpha C；hf_beta C | hm_omega C；hm_psi C |
| 意大利语（i） | if_sara C | im_nicola C |
| 巴西葡萄牙语（p） | pf_dora 未评级 | pm_alex 未评级；pm_santa 未评级 |

注：分组“西班牙语 e”在部分 `kokoro-mlx` README 的一个表格中曾误写成“Other English”；模型作者官方 VOICES.md 与同 README 的 Language Selection 表明确为 Spanish，应以模型作者官方目录为准。

## AINotePro 的显示与数据约束

1. 显示层使用 `语言/地区（口音） → 性别 → 音色名称 + 原始 ID + 官方评级`。例如 `American English / Female / Heart (af_heart) / A`；`British English / Female / Emma (bf_emma) / B-`。原始 ID 是持久化和 API 调用的唯一标识，友好标签只作显示。
2. **不要捏造“甜美、磁性、温柔、少年、播音腔”等没有官方证据的风格标签**；如果未来要做主观描述，必须通过试听评价另行标注“用户标签/主观标签”，不能冒充官方。
3. 官方等级可供排序和筛选，但不应阻止低评级音色的使用；对“未评级”不可误显示为 D 或 F。三个 Voice 区块均可选择不同语言/性别/音色，但只有当前服务端实际支持的组合才允许生成。
4. 服务端的 `list_voices()` 或 Gradio API schema 是**可用音色来源**，官方目录是**元数据来源**；两者交集才是可选列表。缺失元数据时仍可显示原始 ID，且应保留 Profile 原值并标记不可用，不能静默替换。
5. 对跨语言混用，必须显式选择匹配语言的文本和音色；不要在同一段英文文本上仅通过换国家语言的 voice ID 误称“口音多样化”。
6. 当前 `ernestyu/kokoro-tts` 的 `scripts/webui.py` **明确只过滤 `af_/am_/bf_/bm_`**，`synthesize()` 也拒绝其他前缀。当前可用范围仅美式/英式英语共 28 种，尽管底层模型具有更多语言。
7. `kokoro-mlx` 官方 README 声明日语和普通话需要额外 G2P extras：`kokoro-mlx[ja]` / `kokoro-mlx[zh]`；不能假设本机已经安装。其他语言也应实测其 G2P 依赖、输出与发音质量。

## 多语言实施边界

- **Audio V2 第一阶段**：在不修改 Kokoro 服务端的既定边界内，实现英语 28 音色的分组、性别筛选、官方等级与三 Voice 随机；Profile 结构使用通用 `language/locale` 字段，便于以后扩展。
- **多语言扩展阶段（须单独批准）**：如用户决定支持非英语，必须修改 `kokoro-tts` 服务端的音色过滤与校验，安装/验证 G2P extras，新增各语言端到端测试、API 能力探测与兼容性策略；不属于“只改 Anki 插件即可完成”的范围。此阶段不得在未验证时标记“已支持”。

## 来源差异说明

原作者 VOICES.md 以 9 个语言/口音分组计数；模型卡以 8 languages 计数，两者并不矛盾：美式与英式英语是同一种语言的两个口音组。某些社区包装可能增加或减少音色，运行时必须以当前本地服务的返回为准。
