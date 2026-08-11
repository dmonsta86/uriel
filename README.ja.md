<p align="center">
  <img
    src="docs/assets/i18n/ja/uriel-forge-hero.png"
    alt="ウリエルの鍛冶場では、翼のない落ち着いた研究者兼鍛冶師が研究アイデアを鍛え、データ準備、決定論的ソート、証拠追跡、反証、三つの関門、修復、投稿、来歴の記録が周囲に示されている。"
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

> **注記**：本文書は AI 支援による二次レビュー済みです（AI_SECOND_PASS_REVIEWED）。ポスターは AI レビュー済みのローカライズ版（LOCALIZED_AI_REVIEWED）ですが、画像内の可視テキストには母語話者による確認が必要です（AI_ASSISTED_REQUIRES_NATIVE_REVIEW）。修正を歓迎します。

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

リポジトリのチェックアウトから、実行時依存関係やネットワークを使う
隔離ビルドなしでインストールします：

```text
python -m pip install --no-deps --no-build-isolation .
uriel start --root ../my-study --kind new_idea --title "My study" --question "What would change my conclusion?"
uriel status --root ../my-study
uriel verify --root ../my-study
```

配布パッケージ名：`uriel-research`。Python の import 名と CLI
コマンド：`uriel`。

インストール不要の単一ファイル版は
[`docs/GETTING_STARTED_FREE.md`](docs/GETTING_STARTED_FREE.md) を参照してください。

---

<!-- URIEL:SECTION:data-readiness:START -->
## データ準備状態 (ゲート 0)

正規の `main` ブランチでは、実験的なローカル `uriel data` ワークフローにより、UTF-8 の CSV、TSV、JSON、JSONL、テキスト、Markdown を計画して封印し、不変の構造プロファイルとデータ世代を作成し、差分をプレビューし、照合時にすべてのレコードを保持し、元データとの結び付きを独立に再解析・検証できます。数式は実行せず、単位や意味型を推測せず、科学的知見を生成せず、ゲート 0 の権限も付与しません。ゲート 0 は、1 つの正確な世代についてレコード識別子を明示的に宣言した後にのみ開始します。

`uriel data inspect` が世代 ID を返したら、その世代に結び付いた SortSpec を作成して検査します：

```text
uriel readiness init-sort-spec --root ../my-study --generation <GENERATION_ID> --keys id
uriel readiness check --root ../my-study --generation <GENERATION_ID>
uriel readiness status --root ../my-study --generation <GENERATION_ID>
```

v2 レシートは、元データの系譜、パーサーとポリシーの版、安定した列 ID、順序、重複・null 規則、照合、分析計画、および正確なアクティブ SortSpec を結び付けます。欠落、古さ、改変、曖昧さがある状態では下流分析をブロックします。SortSpec が複数ある場合は、正確なパスを明示的に選択してください。

AI 向け世代パケットには PASS レシートと、タスクに必要な行・列の指定が必要です。上限は 1,000 行と 1 MiB で、値の秘匿に対応し、ゲート、公開、知見、Blessing に対する権限はありません。各パケットは助言専用の読み取りモードを宣言し、ネットワーク、shell、パケット書き込み、プロジェクト書き込みを禁止し、要求出力を 128 KiB・15 分以内に制限します。

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

ウリエルの祝福は、実験的なコンテンツアドレス型アテステーション
パッケージです。プロジェクトの正確な世代を、記録されたゲート判定、
レシート、限界、独立検証器の再計算に結び付けます。

これは、その正確に束縛された成果物について記録済みの条件が通過した
ことだけを意味します。独立した科学的検証、著者の暗号署名、査読、
または測定値が真であることの証明ではありません。

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

同梱の合成試練は、解答に封印された 24 件の問題と 100 点の判定基準を
備えた再現可能なフィクスチャです。リリース検査はクリーンな要約を
再計算してフィクスチャを検証しますが、盲検レポートを提出して判定
しない限り、Uriel が問題を検出したとは主張しません。

```text
python scripts/check_forge_trial.py
```

公開 Forge Method はワークフローを説明します。実験的なローカルの
run／state／verifier 基盤は現在利用できます。

```text
uriel forge init --root PROJECT --request INIT.json
uriel forge transition --root PROJECT --snapshot EXACT.json --to-state SCOPED --rationale "Scope reviewed"
uriel forge verify --root PROJECT --snapshot EXACT.json
```

不変の非公開スナップショットを書き込み、上流の権限は一切付与しません。
サニタイズ済みエクスポーターと汎用の blocker-proof／Next-Move 層は
引き続き計画段階です。

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
- Data Desk が報告するのは範囲を限定した構造上・字句上の観察だけです。統計エンジンや意味検証器ではなく、元の測定値や手法を確認する作業の代わりにもなりません。
- AI レンズは助言的なものであり、確定的なゲート決定に対する権威を持ちません。
- ゲートまたは実験的な祝福は、Uriel の記録済み条件が正確に束縛された成果物について通過したことだけを報告します。測定の妥当性、真実、掲載受理、または同業者の合意を確立するものではありません。

---

## Citation and License

引用メタデータは [`CITATION.cff`](CITATION.cff) に記載されています。ライセンスは MIT [`LICENSE`](LICENSE) です。
