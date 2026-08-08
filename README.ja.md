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

> **Notice**: 本文書は AI による二次確認済み翻訳（AI_SECOND_PASS_REVIEWED）です。視覚的注意：上部の画像は英語版のオリジナル（ENGLISH_FALLBACK）です。ネイティブスピーカーによる修正を歓迎します。

<!-- URIEL:SECTION:mission:START -->
### オープンソース・オフラインファーストの研究開発および強化ツールキット

> **あなたのアイデアは鍛冶場（Forge）を生き延びるほど強靭ですか？**
>
> アイデアに対する公平な検証。証拠に対する厳格なテスト。

The Forge of Uriel は、初期の疑問や既存プロジェクトを構造化され再現可能で提出可能な研究へと発展させる支援を行います。

分析前にデータを検証し、重要な主張を直接的な証拠と紐付け、矛盾や限界を保存し、誤解を招くフレーミングや裏付けのない結論を露呈させ、失敗した検証を具体的な修復および提出パスへと変換します。

研究をより強く見せるためではなく、研究の実際の強さとそれをさらに強くする要素を正確に示すために設計されています。

```text
Interpret generously.
Test rigorously.
Report honestly.
```

---

<!-- URIEL:SECTION:status:START -->
## 現在のリリース境界

The Forge of Uriel **1.0.0-rc2** は、オープンソース・オフラインファーストの研究開発および強化ツールキットの公開リリース候補版です。

```text
uriel --version
# uriel 1.0.0rc2
```

---

<!-- URIEL:SECTION:difference:START -->
## 何が違うのか

多くの研究ツールは単一のレイヤー（文献検索、執筆、統計、引用、再現性、査読）のみを扱います。

The Forge of Uriel はチェーン全体を接続するために構築されています。

### アイデアに最も公平な検証機会を与える

拙い表現は思考の貧しさの証拠ではありません。Uriel は元の質問を保存し、最も堅牢な検証可能バージョンを明確にし、競合する解釈を記録し、隠れた前提を特定し、どのような証拠がアイデアを反証するかを問いかけます。

### 結論を出す前にデータを検証する

ゲート 0 は、正確なデータセット生成が識別、ソート、正規化、照合、および鮮度検証に合格するまで、データ依存の結果が権威を得るのを防ぎます。

それまでの誠実な回答は以下の通りです：

> **結果はまだ不明です。**

### 結論を継承された権威ではなく主張として扱う

出版された結論、権威ある著者、自信に満ちたモデル、あるいは長い参考文献一覧も、証拠の代わりにはなりません。

Uriel は問いかけます：

```text
What exactly is being claimed?
Which artifact supports it?
Where is the supporting datapoint?
What contradicts it?
What assumptions does it depend on?
What remains unknown?
What would change the result?
```

### 完成した研究に挑む

3つのゲートは明確さ、証拠、および敵対的整合性をテストします。Uriel は省略された反証、隠れた分母、過度の一般化、因果関係の飛躍、対照のミスマッチ、リーク、脆弱な前提、古い情報源、および結果を超える要約表現を探します。

### 単に批判するのではなく修復する

検証の失敗は曖昧な拒絶で終わるべきではありません。

Uriel は有用な部分を記録し、最小限の誠実な修復を特定し、最も堅牢な次の行動を選択し、安全に準備できるものを準備し、再検証の正確な条件を示します。

---

<!-- URIEL:SECTION:intellectual-honesty:START -->
## 研究はフレーミングによって勝つべきではない

2つの失敗が繰り返し研究を弱体化させます：

1. 反証、帰無結果、限界、または不都合なデータ点が最終的なストーリーから消失すること。
2. 結論が裏付けとなる証拠以上に広範または確実になること。

Uriel はこれらの点を永続的に記録します。何がテストされ、何が失敗し、何が省略され、何が不確実なままであるかを記録します。

---

<!-- URIEL:SECTION:quick-start:START -->
## クイックスタート

プロジェクトのルートで証拠ワークスペースを初期化します：

```text
uriel init
uriel status
uriel verify
```

---

<!-- URIEL:SECTION:data-readiness:START -->
## データ準備状態 (ゲート 0)

データを分析したり結論を出したりする前に、データ準備状態チェックを実行します：

ゲート 0 が失敗した場合、データの完全性が回復するまでダウンストリーム分析はブロックされます。

```text
uriel readiness
```

---

<!-- URIEL:SECTION:gates:START -->
## 3つのゲート (The Three Gates)

### ゲート 1 — 範囲と主張の言語

中心的な主張が正確に定義されているか、用語が一貫しているか、因果関係の飛躍が排除されているかを評価します。

### ゲート 2 — データ準備状態と直接証拠

すべての重要な主張が、直接的で追跡可能な証拠と検証されたデータ生成によって裏付けられていることを要求します。

### ゲート 3 — 敵対的堅牢性と限界

競合する説明、フレーミングバイアス、省略された反証、および適用限界を開示します。

---

<!-- URIEL:SECTION:blessing:START -->
## ウリエルの祝福 (The Blessing of Uriel)

ウリエルの祝福 (*The Blessing of Uriel*) は、署名されコンテンツアドレス指定された監査証明書 (`.ublessing`) です。

研究パケットが厳格な確定性規則の下で3つのゲートすべてを通過したことを示します。祝福は証拠が検証されたことを証明するものであり、査読の代替となるものではありません。

```text
refuted
impossible
```

---

<!-- URIEL:SECTION:ai:START -->
## AI と組み合わせても単体でも Uriel を使用可能

### メンテナーからの注記

The Forge of Uriel の開発には GPT-5.6 Sol の `ultra` モードが広範に使用されました。

これは体験レポートであり、確定的な検証の代わりとなるものではありません。

### 互換性のある AI

互換性のある AI は明確化、整理、下書きを支援できます。

ただし、以下のことは行えません：

```text
mark Data Readiness PASS
pass an integrity gate
change publication authority
override a deterministic failure
issue a Blessing
```

---

<!-- URIEL:SECTION:privacy:START -->
## セキュリティとプライバシー

Uriel は以下に基づいて設計されています：

```text
read-only defaults
exact-root confinement
explicit consent
verified managed copies
immutable generations
```

---

<!-- URIEL:SECTION:trials:START -->
## フォージ試練 (The Forge Trials)

フォージ試練は、Uriel の証拠検証および修復機能の再現可能なベンチマークデモです。

[`docs/FORGE_TRIALS.md`](docs/FORGE_TRIALS.md) および [`benchmarks/forge_trials/synthetic-001/`](benchmarks/forge_trials/synthetic-001/) を参照してください。

---

<!-- URIEL:SECTION:community:START -->
## 貢献

正確性、ポータビリティ、セキュリティ、ドキュメントの向上に貢献する参加を歓迎します。

以下から始めてください：

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SUPPORT.md`](SUPPORT.md)
- [`SECURITY.md`](SECURITY.md)

---

<!-- URIEL:SECTION:limitations:START -->
## 既知の限界

The Forge of Uriel は知的誠実さと証拠の追跡性を強制するために構築されていますが、明確な限界があります：

- Uriel は欠落したデータを捏造したり実験室の測定値を提供したりすることはできません。
- AI レンズは助言的なものであり、確定的なゲート決定に対する権威を持ちません。

---

## Citation and License

引用メタデータは [`CITATION.cff`](CITATION.cff) に記載されています。ライセンスは MIT [`LICENSE`](LICENSE) です。
