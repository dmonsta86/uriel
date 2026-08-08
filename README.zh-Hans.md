<p align="center">
  <img
    src="docs/assets/the-forge-of-uriel/hero.png"
    alt="The Forge of Uriel"
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

> **Notice**: 本文档为 AI 复核翻译（AI_SECOND_PASS_REVIEWED）。视觉说明：顶部图片为英文原版图像（ENGLISH_FALLBACK）。欢迎母语者提出修正意见。

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

在项目根目录下初始化证据工作区：

```text
uriel init
uriel status
uriel verify
```

---

<!-- URIEL:SECTION:data-readiness:START -->
## 数据就绪性 (关卡 0)

在分析数据或得出结论前，运行数据就绪性检查：

若关卡 0 未通过，下游分析将被阻断，直至数据完整性得到恢复。

```text
uriel readiness
```

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

乌列尔的祝福 (*The Blessing of Uriel*) 是一份经过电子签名和内容寻址哈希绑定的审计证书 (`.ublessing`)。

它表明研究包已在严格的确定性规则下成功通过了所有三大关卡。祝福证书仅证明证据已通过验证；它并不赋予神圣权威，也不能替代同行评审。

```text
refuted
impossible
```

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

熔炉考验是可复现的基准演示，展示了 Uriel 的证据检查与修复能力。

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
- AI 视角仅具建议性质，对确定性的关卡决策拥有零权威。
- 通过关卡或获得祝福仅证明证据追溯无误；这并非期刊接收或同行共识的担保。

---

## Citation and License

引用元数据见 [`CITATION.cff`](CITATION.cff)。MIT 许可证见 [`LICENSE`](LICENSE)。
