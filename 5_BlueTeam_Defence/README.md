# LLM 防御技術とは（What's LLM Defence Technology）

基本的に、LLM防御技術は主に**入力処理（Input Processing）**と**出力フィルタリング（Output Filtering）**を指し、LLMリスク管理における最後の防衛線です。

# 入力処理技術（Input Processing Technology）

入力処理は主に、ユーザーからの直接的・間接的なプロンプトを対象としています。

## 1、入力コンテンツチェック（Input Content Checking）
* キーワードフィルタリング手法
* パープレキシティベースの手法
* Redモデルベースの分類器
* Redモデルベースのリスク記述生成
* 機械学習ベースの分類器

## 2、入力セキュリティプロキシ技術（Input Security Proxy Technology）
* 機密質問プロキシ回答システム
* RAG（Retrieval-Augmented Generation）システム

## 3、入力意図認識技術（Input Intent Recognition Technology）
* 意味理解とコンテキスト分析
* 意図分類に基づく処理戦略ルーティング



# 出力フィルタリング技術（Output Filtering Technology）

出力フィルタリングは主に、LLMまたはGenAIアプリが生成する応答コンテンツを対象としています。

## 1、リスクおよび有害コンテンツ検出技術（Risky and Toxic Content Detection Technology）
* Redモデルベースの分類器
* Redモデルベースのラベラー
* Redモデルベースの判定器



# LLMセキュリティにおけるLLM防御技術の役割（What role does LLM Defense Technology play in LLM Security）

LLM防御技術は、大規模モデルを変更することなく、プラグイン型のセキュリティ防御システムを実装するものです。この技術の主な目標は迅速な損失停止を達成すること、すなわち、潜在的に有害な入力・出力コンテンツを正確にフィルタリングすることで、不適切な情報の拡散を素早く防止することです。LLM防御の実装は通常、基本的なキーワードフィルタリングからより複雑な意味理解と状況分析、そしてプロキシモデルまで、複数のレイヤーの検査メカニズムを含み、各レイヤーは潜在的な不適切コンテンツを識別し処理するように設計されています。

例えば：
* 出力検出：モデル出力の前にリアルタイムコンテンツレビューシステムを追加し、生成されたすべてのコンテンツを評価できます。有害と判定された出力は即座にインターセプトされ修正されます。
* 入力検出：シナリオ分析と意図認識において、害を引き起こす可能性のある入力をプロキシモデルの応答に導入し、リスク問題における安全性を確保します。

さらに、LLM防御は内生的セキュリティの効果的な補完です。内生的セキュリティがモデル自体のセキュリティを改善することで不適切な出力の可能性を低減する一方、外部のLLM防御技術は追加の保護レイヤーを提供します。この二重保護メカニズムにより、内生的セキュリティ対策が不適切な動作を完全に防止できなかった場合でも、外部介入によって問題を迅速に修正でき、全体的なセキュリティシステムの堅牢性が大幅に強化されます。


# 従来のコンテンツセキュリティと比較したLLM防御の新たな課題（Compared with traditional content security, what new challenges of LLM Defence）

従来のコンテンツレビュー技術は主にユーザー生成コンテンツ（UGC）と専門家生成コンテンツ（PGC）のレビューシナリオに対応しています。これらはナラティブベースで比較的固定されており、標準化が容易です。しかし、従来のコンテンツレビュー技術は生成型の大規模モデル、特にマルチターン対話の実装に使用されるものには適していません。これらの大規模モデルは対話中にトピックの一貫性と論理を維持できますが、質問自体は単独では必ずしも機密コンテンツを含まず、マルチターン対話のコンテキストで不適切なコンテンツを生成する可能性があります。

さらに、特定の入力を通じてモデルに不適切な回答を生成させるなどの多くのシナリオベースの攻撃は、従来のコンテンツレビュー技術では予測・解決が困難です。これらの攻撃は大規模モデルの不確実性といわゆる「ハルシネーション」特性を利用しています。つまり、モデルが誤った事実や論理に基づいて回答を生成する可能性があります。この不確実性と大規模モデル自体の複雑さが、検出とレビューの難易度を高めています。

したがって、これらのモデルの特性に基づいて、生成型大規模モデルのセキュリティ要件を完全に満たす新しいコンテンツレビュー技術を構築する必要があります。これには、マルチターン対話のコンテキストを理解・分析できるインテリジェントツールの開発や、機械学習手法を使用した不適切なコンテンツ生成の予測・識別が含まれます。この新技術には、会話のダイナミクスと複雑さ、およびモデル生成応答の内在的ロジックのより深い理解が必要であり、より正確でリアルタイムなコンテンツセキュリティソリューションを提供します。


# オープンソースプロジェクト（Open-Source project）
* [PurpleLlama](https://github.com/meta-llama/PurpleLlama/tree/main)
* [Guardrails AI](https://www.guardrailsai.com/)
* [guardrails](https://github.com/guardrails-ai/guardrails)
* [Guardrails Hub](https://www.guardrailsai.com/docs/concepts/hub)
* [LangKit](https://github.com/whylabs/langkit)


# 無料アクセス製品（Free-access Products）
- [Epivolis/Hyperion](https://huggingface.co/Epivolis/Hyperion)
- [fmops/distilbert-prompt-injection](https://huggingface.co/fmops/distilbert-prompt-injection)
- [deepset/deberta-v3-base-injection](https://huggingface.co/deepset/deberta-v3-base-injection)
- [Myadav/setfit-prompt-injection-MiniLM-L3-v2](https://huggingface.co/Myadav/setfit-prompt-injection-MiniLM-L3-v2)
- [rebuff: A self-hardening prompt injection detector](https://github.com/protectai/rebuff/tree/main)
- [Vigil: Security scanner for Large Language Model (LLM) prompts](https://github.com/deadbits/vigil-llm)
- [llm-guard](https://github.com/protectai/llm-guard)
  - [llm-guard-playground](https://huggingface.co/spaces/protectai/llm-guard-playground)

# 商用製品（Commercial Products）
* [Microsoft Prompt Shields](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection#prompt-shields-for-documents)

# Hugging Face モデル（Huggingface Models）
* [martin-ha/toxic-comment-model](https://huggingface.co/martin-ha/toxic-comment-model)
