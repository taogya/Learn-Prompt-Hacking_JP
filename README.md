<p align="center">

<h1 align="center">Learn Prompt Hacking（日本語版）</h1>

<p align="center">
<p>
<img alt="GitHub Contributors" src="https://img.shields.io/github/contributors/TrustAI-laboratory/Learn-Prompt-Hacking" />
<img alt="GitHub Last Commit" src="https://img.shields.io/github/last-commit/TrustAI-laboratory/Learn-Prompt-Hacking" />
<img alt="" src="https://img.shields.io/github/repo-size/TrustAI-laboratory/Learn-Prompt-Hacking" />
<!--<img alt="Downloads" src="https://static.pepy.tech/badge/Learn-Prompt-Hacking" />-->
<img alt="GitHub Issues" src="https://img.shields.io/github/issues/TrustAI-laboratory/Learn-Prompt-Hacking" />
<img alt="GitHub Pull Requests" src="https://img.shields.io/github/issues-pr/TrustAI-laboratory/Learn-Prompt-Hacking" />
<img alt="Github License" src="https://img.shields.io/github/license/TrustAI-laboratory/Learn-Prompt-Hacking" />
</p>

![t0151f1fc4110babf75](https://github.com/user-attachments/assets/9a6eb026-82b5-40ae-adff-2d61147e22b1)

> **注意**: この日本語版は [TrustAI-laboratory/Learn-Prompt-Hacking](https://github.com/TrustAI-laboratory/Learn-Prompt-Hacking) をフォークし、教材コンテンツを日本語に翻訳したものです。また、OpenAI API の代わりに [GitHub Models](https://github.com/marketplace/models) を利用できるよう `utils/llm_client.py` を追加しています。

最も包括的なプロンプトハッキングコースです。プロンプトエンジニアリングとプロンプトハッキングに関する学習の進捗を記録しています。
- プロンプトエンジニアリング技術
- GenAI 開発技術
- プロンプトハッキング技術
  - ChatGPT ジェイルブレイク
  - GPT アシスタントのプロンプト漏洩
  - GPTs プロンプトインジェクション
  - LLM プロンプトセキュリティ
  - スーパープロンプト
  - プロンプトハック
  - プロンプトセキュリティ
  - 敵対的機械学習
- LLM セキュリティ防御技術
- LLM ハッキングリソース
- LLM セキュリティ論文
- カンファレンススライド


# 背景（Background）
ChatGPT のリリースにより、LLM はますます主流となり、AI システムとのインタラクション方法に革命をもたらしました。ChatGPT 以前にも、Vaswani らによる「Attention is All You Need」論文、BERT、GPT-2、GPT-3、T5、RoBERTa、ELECTRA、ALBERT など、この革命の基盤を築いた NLP における注目すべき進歩がいくつかありました。

これらの進歩は非常に重要ですが、一般の人々には広く知られていないかもしれません。2023年は、生成タスクのためにこれらの汎用モデルが様々な産業で大量採用されるターニングポイントとなりました。

データサイエンティストや AI 開発者として、継続的な学習は重要な素養であり、AI 駆動の自然言語処理の時代に最適なソリューションを提供するために、LLM の最新技術に精通し続けることが不可欠です。

一方で、AI の急速な到来は IT ソフトウェアエコシステム全体に多数の新しい攻撃面とリスクをもたらしました。データサイエンティストや開発者も LLM のセキュリティ問題に注意を払う必要があります。


# コースの目的（Course Objective）
このコースの主な目標は以下の通りです：
* LLM との効果的なインタラクションのためのプロンプトエンジニアリング技術を深く理解すること。これらの戦略を習得することで、自然言語の力を活用した革新的で効果的かつ効率的なソリューションを開発する能力を向上させることを目指します。
* LLM アプリケーションが直面するリスクの基本的な理解を得て、GenAI アプリのリスクを軽減または防止する方法を学ぶこと。

# その他のリソース（Other resources）
* [Tech Blog](https://securaize.substack.com/)

# ライセンス（License）

## 本リポジトリ

このリポジトリは [TrustAI-laboratory/Learn-Prompt-Hacking](https://github.com/TrustAI-laboratory/Learn-Prompt-Hacking) をフォークし、教材コンテンツを日本語に翻訳・改変したものです。原著のライセンスに基づき、同じ MIT License の下で公開しています。

- 原著: Copyright (c) 2024 TrustAI Pte. Ltd. — [MIT License](LICENSE)

## 同梱データセット

`resources/csv` ディレクトリには、以下の外部データセットを翻訳・改変したファイルが含まれています。各データセットには元のライセンスが適用されます。

### llm-attacks — harmful_behaviors.csv

- 出典: [llm-attacks/llm-attacks](https://github.com/llm-attacks/llm-attacks) (Andy Zou et al.)
- ライセンス: MIT License — [resources/csv/llm-attacks/LICENSE.txt](resources/csv/llm-attacks/LICENSE.txt)
- 改変内容: 日本語に翻訳 (`harmful_behaviors_ja.csv`)

### tatsu-lab — alpaca_instructions.csv

- 出典: [tatsu-lab/stanford_alpaca](https://github.com/tatsu-lab/stanford_alpaca) (Stanford Alpaca)
- ライセンス: Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) — [resources/csv/tatsu-lab/DATA_LICENSE.txt](resources/csv/tatsu-lab/DATA_LICENSE.txt)
- 改変内容: 日本語に翻訳 (`alpaca_instructions_ja_apple-translate.csv`, `alpaca_instructions_ja_gemma3-4b.csv`)
