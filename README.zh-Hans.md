<p align="center">
  <img
    src="docs/assets/i18n/zh-Hans/uriel-forge-hero.png"
    alt="乌列尔之炉描绘一位无翼、沉着而警觉的学者型锻造师，在铁砧前检验研究想法，周围呈现数据就绪、确定性排序、证据追踪、反证、三道关卡、修复、投稿与溯源凭证。"
    width="100%"
  >
</p>

<p align="center">
  <a href="https://github.com/dmonsta86/uriel/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/dmonsta86/uriel/actions/workflows/ci.yml/badge.svg">
  </a>
  <img alt="Status: public beta" src="https://img.shields.io/badge/status-public%20beta-f59e0b">
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-3776AB">
  <a href="LICENSE">
    <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-22c55e">
  </a>
  <img alt="Runtime dependencies: zero" src="https://img.shields.io/badge/runtime%20dependencies-0-0f766e">
</p>

<p align="center">
  🌐 <strong>Languages:</strong>
  <a href="README.md">English</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.pt-BR.md">Português (Brasil)</a> |
  <a href="README.zh-Hans.md">简体中文</a> |
  <a href="README.ar.md">العربية</a> |
  <a href="README.hi.md">हिन्दी</a> |
  <a href="README.ja.md">日本語</a>
</p>

# The Forge of Uriel

> **说明**：本文档已完成 AI 辅助二次复核（AI_SECOND_PASS_REVIEWED）。海报为经 AI 复核的本地化版本（LOCALIZED_AI_REVIEWED），但其中可见文字仍需母语者复核（AI_ASSISTED_REQUIRES_NATIVE_REVIEW）。欢迎提出修正。

<!-- URIEL:SECTION:mission:START -->
### 开源、离线优先的科研开发与强化工具包

> **你的想法足够坚固，能经受住熔炉的考验吗？**
>
> 给想法一个公正的审视。对证据进行严格的检验。

The Forge of Uriel 旨在将初步疑问和现有项目转化为结构化、可复现、具备提交条件的科研成果。

它在分析前验证数据，将关键主张追溯至直接证据，保留矛盾与局限性，揭露误导性话术与缺乏支撑的结论，并将未通过的检查转化为具体的修复与提交路径。

它的目的不是让研究听起来更强大，而是确切展示研究的实际强度——以及如何使其更加坚固。

```text
Interpret generously.
Test rigorously.
Report honestly.
```

---

<!-- URIEL:SECTION:status:START -->
## 当前发布边界

The Forge of Uriel **1.0.0-rc2** 是开源、离线优先科研开发与强化工具包的公开候选版本。

```text
uriel --version
# uriel 1.0.0rc2
```

---

<!-- URIEL:SECTION:difference:START -->
## 有何不同

大多数科研工具仅处理单一环节：文献搜索、写作、统计、引用、可复现性或评审。

The Forge of Uriel 旨在连接整个完整链条。

### 给予想法最公正的审视

表述欠佳绝非思想贫瘠的证据。Uriel 保留原始疑问，明确最具可检验性的版本，记录竞争性解释，识别隐藏假设，并探寻何种证据能够证伪该想法。

### 在得出结论前验证数据

关卡 0 (Gate 0) 防止依赖数据的结论在数据集确切版本未通过身份、排序、规范化、对账及陈旧性检查前获得权威认可。

在此之前，坦诚的回答是：

> **结果目前尚不可知。**

### 将结论视为待证实的主张，而非继承的权威

已发表的结论、声名显赫的作者、自信的模型或长篇参考文献均不能替代确凿的证据。

Uriel 追问：

```text
What exactly is being claimed?
Which artifact supports it?
Where is the supporting datapoint?
What contradicts it?
What assumptions does it depend on?
What remains unknown?
What would change the result?
```

### 挑战完成的工作

三大关卡检验清晰度、证据链及对抗完整性。Uriel 查找被遗漏的反面证据、隐藏的分母、过度泛化、因果冒进、对照错配、数据泄漏、脆弱假设、陈旧来源以及超出底层结果的总结性语言。

### 修复而非仅仅批评

检查未通过不应止于含糊的拒绝。

Uriel 记录仍有价值的部分，确定最小的坦诚修复方案，选择最坚固的下一步行动，安全地准备可准备的内容，并明确复核的确切条件。

---

<!-- URIEL:SECTION:intellectual-honesty:START -->
## 科研不应靠话术取胜

两大常见缺陷不断削弱科研质量：

1. 反面证据、零结果、局限性或尴尬的数据点在最终成果中悄然消失；
2. 得出的结论超出了底层证据所能支撑的范围或确定性。

Uriel 使这些关键点保持持久记录。它记录了测试内容、失败项目、遗漏事项以及仍不确定的部分。

---

<!-- URIEL:SECTION:quick-start:START -->
## 快速开始

从仓库检出版本安装；不安装运行时依赖，也不使用需要联网的隔离构建：

```text
python -m pip install --no-deps --no-build-isolation .
uriel start --root ../my-study --kind new_idea --title "My study" --question "What would change my conclusion?"
uriel status --root ../my-study
uriel verify --root ../my-study
```

发行包名：`uriel-research`。Python 导入名及 CLI 命令：`uriel`。

无需安装的单文件用法见
[`docs/GETTING_STARTED_FREE.md`](docs/GETTING_STARTED_FREE.md)。

---

<!-- URIEL:SECTION:data-readiness:START -->
## 数据就绪性 (关卡 0)

在规范的 `main` 分支上，实验性的本地 `uriel data` 工作流可以规划并封存 UTF-8 编码的 CSV、TSV、JSON、JSONL、文本和 Markdown；创建不可变的结构化剖析与数据代；预览差异；在对账时保留每条记录；并独立重新解析和验证原始数据绑定。它不会执行公式、猜测单位或语义类型、生成科学发现，也不会授予关卡 0 权限。只有在你为某个精确数据代明确声明记录身份后，关卡 0 才会开始。

当 `uriel data inspect` 返回数据代 ID 后，创建并检查与该数据代绑定的 SortSpec：

```text
uriel readiness init-sort-spec --root ../my-study --generation <GENERATION_ID> --keys id
uriel readiness check --root ../my-study --generation <GENERATION_ID>
uriel readiness status --root ../my-study --generation <GENERATION_ID>
```

v2 收据会绑定原始数据血缘、解析器和策略版本、稳定列 ID、顺序、重复值和空值规则、对账、分析计划以及精确的当前 SortSpec。状态缺失、过期、遭到篡改或含糊时，下游分析会被阻断。如果存在多个 SortSpec，请明确选择其精确路径。

面向 AI 的数据代数据包必须具有 PASS 收据，并明确指定任务所需的行和列。其上限为 1,000 行和 1 MiB，支持隐藏数值，且不具有任何关卡、发布、发现或 Blessing 权限。每个数据包都声明仅供建议、只读使用：禁止网络、shell、数据包写入和项目写入，并将请求的输出限制为 128 KiB 和 15 分钟。

---

<!-- URIEL:SECTION:forge-forward:START -->
## 继续未完成的 Forge 运行

实验性 Forge 命令基于精确的按内容寻址路径运行，绝不基于可变的 "latest" 运行：

```text
uriel forge continue --root ../my-study --snapshot <EXACT_SNAPSHOT> --request artifacts/forge-forward.json
uriel forge verify-continuation --root ../my-study --packet <EXACT_CONTINUATION>
uriel forge export --root ../my-study --snapshot <EXACT_SNAPSHOT> --destination exports/review-copy
uriel forge verify-export --root ../my-study --manifest exports/review-copy/manifest.json --snapshot <EXACT_SNAPSHOT>
```

延续包保留在被忽略的 `.uriel/forge/` 状态下的私有状态。导出是仅包含生成的结构元数据和别名的新目录。它们不会复制证据主体、项目/运行 ID、私有路径、凭据、私有 URL 或无关名称。每个验证器都会重新读取精确源，重新计算哈希和排名，拒绝额外的文件或链接，并报告零 Gate、发布、验证器、Blessing 或 Earned Wings 权限。

有关闭合请求形式、评分规则、阻碍因素推导和拒绝边界，请参见 [Forge 方法](docs/FORGE_METHOD.md)。

---

<!-- URIEL:SECTION:gates:START -->
## 三大关卡

### 关卡 1 — 范围与主张语言

评估核心主张是否被精确界定、术语是否前后一致，并消除因果冒进或过度泛化。

### 关卡 2 — 数据就绪性与直接证据

要求每一项重大主张都必须有可追溯的直接证据和已验证的数据生成所支撑。

### 关卡 3 — 对抗鲁棒性与局限性

揭露竞争性解释、框架偏见、被遗漏的反面证据以及适用性限制。

---

<!-- URIEL:SECTION:blessing:START -->
## 乌列尔的祝福 (The Blessing of Uriel)

乌列尔的祝福是一种实验性的内容寻址证明包。它把项目的精确版本与
Uriel 记录的关卡判定、凭证、局限性及独立验证器的重新计算绑定在一起。

它只表示这些记录的判定条件对这些精确绑定的工件成立；它不是独立的
科学验证、作者的加密签名、同行评审，也不能证明底层测量必然为真。

---

<!-- URIEL:SECTION:ai:START -->
## 无论是否结合 AI 均可使用 Uriel

### 维护者说明

The Forge of Uriel 在开发过程中大量使用了 GPT-5.6 Sol 的 `ultra` 模式，维护者推荐将其用于深度的长跨度研究和对抗性检验。

这属于经验分享，并非硬性依赖、独家绑定、隐私背书或替代确定性验证的工具。亦可使用其他有能力的 AI 系统。

### 兼容的 AI

兼容的 AI 可以帮助澄清、组织、起草和批判。

但它绝不能：

```text
mark Data Readiness PASS
pass an integrity gate
change publication authority
override a deterministic failure
issue a Blessing
```

---

<!-- URIEL:SECTION:privacy:START -->
## 安全与隐私

Uriel 围绕以下核心原则设计：

```text
read-only defaults
exact-root confinement
explicit consent
verified managed copies
immutable generations
```

---

<!-- URIEL:SECTION:trials:START -->
## 熔炉考验 (The Forge Trials)

内置合成考验是一套可复现夹具，答案中封存了 24 个问题，并配有
100 分裁决量表。发布检查会重新计算清洗后的摘要并验证夹具完整性；
若没有先提交并裁决盲测报告，它不会声称 Uriel 检出了任何问题。

```text
python scripts/check_forge_trial.py
```

公开的 Forge Method 描述工作流程。其实验性的本地运行、状态与验证主干现已可用：

```text
uriel forge init --root PROJECT --request INIT.json
uriel forge transition --root PROJECT --snapshot EXACT.json --to-state SCOPED --rationale "Scope reviewed"
uriel forge verify --root PROJECT --snapshot EXACT.json
```

它写入不可变的私有快照，不授予任何上游权限。净化导出器及通用的阻塞证明／下一步层仍在规划中。

请参阅 [`docs/FORGE_TRIALS.md`](docs/FORGE_TRIALS.md) 与 [`benchmarks/forge_trials/synthetic-001/`](benchmarks/forge_trials/synthetic-001/)。

---

<!-- URIEL:SECTION:community:START -->
## 贡献指南

欢迎提高准确性、便携性、安全性、文档质量、翻译水平和工作流的贡献。

请从以下文档开始：

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SUPPORT.md`](SUPPORT.md)
- [`SECURITY.md`](SECURITY.md)

---

<!-- URIEL:SECTION:limitations:START -->
## 已知局限性

The Forge of Uriel 旨在贯彻求真务实的态度与证据追溯，但其具有明确的边界：

- Uriel 无法凭空捏造缺失的数据或提供实验室测量值。
- Data Desk 只报告有界的结构与词法观察；它不是统计引擎或语义验证器，也不能取代对原始测量和方法的检查。
- AI 视角仅具建议性质，对确定性的关卡决策拥有零权威。
- 关卡或实验性祝福只报告 Uriel 记录的判定条件对精确绑定工件成立；它不确立测量有效性、真理、期刊接收或同行共识。

---

## Citation and License

引用元数据见 [`CITATION.cff`](CITATION.cff)。MIT 许可证见 [`LICENSE`](LICENSE)。
