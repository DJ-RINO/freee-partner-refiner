# freee-partner-refiner 使用例ドキュメント

このドキュメントでは、freee-partner-refiner の各種コンポーネントの使用方法を説明します。

---

## 1. 基本的な使い方

### 1.1 取引処理（transaction_processor.py）

銀行/カード明細から取引先を特定し、freee取引先に紐付けるメインスクリプトです。

#### 基本コマンド

```bash
python transaction_processor.py transactions.csv --limit 10
```

#### 入力CSVフォーマット

CSVファイルは以下の形式で作成してください:

| カラム名 | 必須 | 説明 |
|---------|------|------|
| id / ID | はい | 取引ID |
| name / 取引先名 / 取引先 | はい | 明細に記載された取引先名 |
| amount | いいえ | 金額 |
| date / 日付 | いいえ | 取引日 |

**入力CSVの例:**

```csv
id,name,amount,date
1,トイザラス熊本店,5000,2026-01-01
2,セブンイレブン代々木,1200,2026-01-02
3,スターバックス新宿,850,2026-01-03
```

#### コマンドラインオプション

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--limit N` | 10 | 最大処理件数（0で無制限） |
| `--threshold N` | 0.6 | 紐付け閾値（0.0 - 1.0） |
| `--no-cache` | - | 親会社特定のキャッシュを使用しない |
| `--execute` | - | 実際に更新を実行（デフォルトはドライラン） |

#### 必要な環境変数

```bash
export FREEE_ACCESS_TOKEN="your_freee_access_token"
export FREEE_COMPANY_ID="your_company_id"
export ANTHROPIC_API_KEY="your_anthropic_api_key"
```

#### 使用例

```bash
# ドライラン（最初の10件のみ処理）
python transaction_processor.py transactions.csv --limit 10

# 全件処理（ドライラン）
python transaction_processor.py transactions.csv --limit 0

# 閾値を変更して処理
python transaction_processor.py transactions.csv --threshold 0.7

# 実際に更新を実行（注意: 本番データが変更されます）
python transaction_processor.py transactions.csv --limit 10 --execute

# キャッシュを使用せずに処理
python transaction_processor.py transactions.csv --no-cache
```

#### 出力ファイル

処理完了後、以下のファイルが生成されます:

- `transaction_results_YYYYMMDD_HHMMSS.csv` - 処理結果
- `link_proposals_YYYYMMDD_HHMMSS.csv` - 紐付け提案レポート

---

### 1.2 バッチ処理（batch_processor.py）

freee取引先の法人情報を一括で補完するツールです。手動（AI貼り付け）と自動（Claude API）の2つのワークフローに対応しています。

#### 手動ワークフロー

AIに情報を貼り付けて結果を取得する方式です。

```bash
python batch_processor.py manual
```

**ワークフロー:**

1. freeeから取引先をエクスポート
2. prompts/batch_lookup_prompt.md を開き、プロンプトをAI（Claude/ChatGPT）に貼り付け
3. エクスポートしたデータを貼り付け
4. AIの出力を `ai_result.csv` として保存
5. 結果をインポート（確認後に実行）

#### 自動ワークフロー

Claude APIを使用して自動的に法人情報を調査します。

```bash
# 最初の10件のみ処理（デフォルト）
python batch_processor.py auto

# 処理件数を指定
python batch_processor.py auto --limit 10

# 全件処理
python batch_processor.py auto --limit 0
```

#### コマンドラインオプション

| モード | オプション | 説明 |
|-------|-----------|------|
| `manual` | - | 手動ワークフロー（AI貼り付け方式） |
| `auto` | `--limit N` | 自動ワークフロー（デフォルト10件、0で無制限） |

#### 必要な環境変数

```bash
export FREEE_ACCESS_TOKEN="your_freee_access_token"
export FREEE_COMPANY_ID="your_company_id"
export ANTHROPIC_API_KEY="your_anthropic_api_key"  # autoモードで必須
```

#### 出力ファイル

- `auto_result_YYYYMMDD_HHMMSS.csv` - 調査結果

---

## 2. プログラムからの利用

### 2.1 親会社特定（ParentCompanyFinder）

銀行/カード明細の取引先名から、正式な法人名を特定します。

```python
from parent_company_finder import ParentCompanyFinder

# 初期化（APIキーは環境変数からも取得可能）
finder = ParentCompanyFinder(anthropic_api_key="your_api_key")

# 親会社を特定
result = finder.find_parent_company("セブンイレブン代々木")

# 結果を確認
print(f"元の名前: {result['original_name']}")
print(f"親会社: {result['parent_company']}")  # 株式会社セブン-イレブン・ジャパン
print(f"確信度: {result['confidence']}")      # high / medium / low / unknown
print(f"理由: {result['reasoning']}")
print(f"個人事業主の可能性: {result['is_individual']}")
print(f"備考: {result['notes']}")
```

#### 一括処理

```python
# 複数の取引先名を一括処理
names = ["トイザラス熊本店", "ファミリーマート渋谷店", "スターバックス新宿"]
results = finder.find_parent_companies_batch(names)

for result in results:
    print(f"{result['original_name']} -> {result['parent_company']}")
```

#### キャッシュ操作

```python
# キャッシュを使用しない
result = finder.find_parent_company("セブンイレブン代々木", use_cache=False)

# キャッシュをクリア
deleted_count = finder.clear_cache()
print(f"{deleted_count}件のキャッシュを削除しました")
```

#### 初期化オプション

```python
finder = ParentCompanyFinder(
    anthropic_api_key="your_api_key",          # APIキー（省略時は環境変数から取得）
    cache_dir="/path/to/cache",                # キャッシュディレクトリ
    model="claude-sonnet-4-20250514"           # 使用するClaudeモデル
)
```

---

### 2.2 マッチング（PartnerMatcher）

freee既存取引先と親会社名をマッチングし、紐付け候補を提案します。

```python
from partner_matcher import PartnerMatcher, MatchConfig, PartnerData

# freee取引先データを準備
partners: list[PartnerData] = [
    {
        "id": 1,
        "name": "株式会社セブン-イレブン・ジャパン",
        "shortcut1": "セブンイレブン",
        "shortcut2": None,
        "long_name": None,
        "corporate_number": "8011101021428"
    },
    {
        "id": 2,
        "name": "日本トイザらス株式会社",
        "shortcut1": "トイザらス",
        "shortcut2": None,
        "long_name": None,
        "corporate_number": "4010401089234"
    }
]

# マッチャーを初期化
matcher = PartnerMatcher(partners)

# 名前でマッチング
candidates = matcher.match_by_name("株式会社セブン-イレブン・ジャパン")

# 候補を確認
for candidate in candidates:
    print(f"取引先: {candidate['partner']['name']}")
    print(f"スコア: {candidate['score']:.2f}")
    print(f"マッチタイプ: {candidate['match_type']}")  # exact_name / partial_match / name_similarity
    print(f"マッチフィールド: {candidate['matched_field']}")  # name / shortcut1 / shortcut2 / long_name
```

#### 法人番号での完全一致検索

```python
# 法人番号で検索（完全一致のみ）
partner = matcher.match_by_corporate_number("8011101021428")
if partner:
    print(f"見つかりました: {partner['name']}")
```

#### 最適なマッチを1件取得

```python
# 最適な候補を1件だけ取得
best_match = matcher.find_best_match(
    parent_company="株式会社セブン-イレブン・ジャパン",
    corporate_number="8011101021428"  # オプション
)

if best_match:
    print(f"最適な候補: {best_match['partner']['name']} (スコア: {best_match['score']:.2f})")
```

#### マッチング設定（MatchConfig）

```python
from partner_matcher import MatchConfig

config = MatchConfig(
    min_score=0.6,            # 最低スコア閾値（これ以下は候補から除外）
    max_candidates=5,         # 最大候補数
    exact_match_boost=0.3,    # 完全一致時のボーナススコア
    corp_num_weight=1.0       # 法人番号一致の重み
)

matcher = PartnerMatcher(partners, config=config)
```

---

### 2.3 紐付け実行（PartnerLinker）

マッチング結果を元に、freee取引先への紐付けを提案・実行します。

```python
from partner_linker import PartnerLinker, LinkConfig, LinkReportGenerator
from partner_matcher import PartnerMatcher

# マッチャーを準備
matcher = PartnerMatcher(partners)

# リンカーを初期化
config = LinkConfig(
    auto_link_threshold=0.9,      # 自動紐付けの閾値
    suggest_threshold=0.6,        # 提案表示の閾値
    create_new_if_no_match=True,  # マッチなしの場合に新規作成を提案
    dry_run=True                  # ドライラン（実際には更新しない）
)
linker = PartnerLinker(access_token="your_freee_token", config=config)

# マッチング候補を取得
candidates = matcher.match_by_name("株式会社セブン-イレブン・ジャパン")

# 紐付け提案を作成
proposal = linker.create_proposal(
    transaction_name="セブンイレブン代々木",
    parent_company="株式会社セブン-イレブン・ジャパン",
    corporate_number="8011101021428",  # オプション
    candidates=candidates
)

# 提案を確認
print(f"アクション: {proposal['action']}")          # link / create / skip
print(f"紐付け先: {proposal['target_partner']}")    # PartnerDataまたはNone
print(f"スコア: {proposal['match_score']:.2f}")
print(f"確信度: {proposal['confidence']}")          # high / medium / low / unknown
print(f"理由: {proposal['reason']}")
```

#### 紐付けを実行

```python
# 実行モードでリンカーを初期化
linker = PartnerLinker(
    access_token="your_freee_token",
    config=LinkConfig(dry_run=False)  # 実行モード
)

# 紐付けを実行
result = linker.execute_link(
    company_id=12345,
    proposal=proposal
)

print(f"ステータス: {result['status']}")  # success / failed / skipped
print(f"メッセージ: {result['message']}")
print(f"パートナーID: {result['partner_id']}")
```

#### レポート生成

```python
# レポートジェネレーターを使用
reporter = LinkReportGenerator()

# 提案を追加
reporter.add_proposal(proposal)

# レポートを生成
proposal_report_path = reporter.generate_proposal_report()  # link_proposals_*.csv
print(f"提案レポート: {proposal_report_path}")

# サマリーを表示
reporter.print_summary()
```

---

## 3. 設定オプション

### 3.1 ProcessorConfig（取引処理設定）

`TransactionProcessor` で使用する設定です。

```python
from transaction_processor import ProcessorConfig

config = ProcessorConfig(
    use_cache=True,              # 親会社特定のキャッシュを使用
    auto_link_threshold=0.9,     # 自動紐付け閾値（これ以上で自動紐付け）
    suggest_threshold=0.6,       # 提案表示閾値（これ以上で候補として表示）
    dry_run=True,                # ドライラン（Falseで実際に更新）
    max_transactions=0           # 最大処理件数（0で無制限）
)
```

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| use_cache | bool | True | 親会社特定のキャッシュを使用するか |
| auto_link_threshold | float | 0.9 | この閾値以上のスコアで自動紐付け |
| suggest_threshold | float | 0.6 | この閾値以上のスコアで候補として表示 |
| dry_run | bool | True | True=ドライラン / False=実際に更新 |
| max_transactions | int | 0 | 最大処理件数（0=無制限） |

---

### 3.2 MatchConfig（マッチング設定）

`PartnerMatcher` で使用する設定です。

```python
from partner_matcher import MatchConfig

config = MatchConfig(
    min_score=0.6,            # 最低スコア閾値
    max_candidates=5,         # 最大候補数
    exact_match_boost=0.3,    # 完全一致ボーナス
    corp_num_weight=1.0       # 法人番号一致の重み
)
```

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| min_score | float | 0.6 | この閾値未満のスコアは候補から除外 |
| max_candidates | int | 5 | 返却する最大候補数 |
| exact_match_boost | float | 0.3 | 正規化後の完全一致時に加算するボーナス |
| corp_num_weight | float | 1.0 | 法人番号一致時の重み付け |

---

### 3.3 LinkConfig（紐付け設定）

`PartnerLinker` で使用する設定です。

```python
from partner_linker import LinkConfig

config = LinkConfig(
    auto_link_threshold=0.9,      # 自動紐付けの閾値
    suggest_threshold=0.6,        # 提案表示の閾値
    create_new_if_no_match=True,  # マッチなしの場合に新規作成を提案
    dry_run=True                  # ドライラン
)
```

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| auto_link_threshold | float | 0.9 | この閾値以上で自動的に紐付け |
| suggest_threshold | float | 0.6 | この閾値以上で紐付け候補として提案 |
| create_new_if_no_match | bool | True | マッチなしの場合に新規作成を提案するか |
| dry_run | bool | True | True=ドライラン / False=実際にAPIを呼び出し |

---

## 4. データ型定義

### 4.1 PartnerData（取引先データ）

freee取引先のデータ構造です。

```python
from partner_matcher import PartnerData

partner: PartnerData = {
    "id": 1,                                       # 取引先ID
    "name": "株式会社セブン-イレブン・ジャパン",    # 取引先名
    "shortcut1": "セブンイレブン",                  # ショートカット1
    "shortcut2": None,                             # ショートカット2
    "long_name": None,                             # 正式名称
    "corporate_number": "8011101021428"            # 法人番号
}
```

### 4.2 ParentCompanyResult（親会社特定結果）

```python
from parent_company_finder import ParentCompanyResult

result: ParentCompanyResult = {
    "original_name": "セブンイレブン代々木",        # 元の名前
    "parent_company": "株式会社セブン-イレブン・ジャパン",  # 特定された親会社名
    "confidence": "high",                          # 確信度
    "reasoning": "判断理由...",                    # 判断理由
    "is_individual": False,                        # 個人事業主の可能性
    "notes": ""                                    # 補足情報
}
```

### 4.3 MatchCandidate（マッチング候補）

```python
from partner_matcher import MatchCandidate

candidate: MatchCandidate = {
    "partner": partner,           # PartnerData
    "score": 0.95,                # マッチスコア（0.0 - 1.0）
    "match_type": "exact_name",   # exact_corp_num / exact_name / partial_match / name_similarity
    "matched_field": "name"       # name / shortcut1 / shortcut2 / long_name / corporate_number
}
```

### 4.4 LinkProposal（紐付け提案）

```python
from partner_linker import LinkProposal

proposal: LinkProposal = {
    "transaction_name": "セブンイレブン代々木",     # 明細の取引先名
    "parent_company": "株式会社セブン-イレブン・ジャパン",  # 特定された親会社名
    "corporate_number": "8011101021428",           # 法人番号
    "action": "link",                              # link / create / skip
    "target_partner": partner,                     # 紐付け先（linkの場合）
    "match_score": 0.95,                          # マッチスコア
    "confidence": "high",                          # high / medium / low / unknown
    "reason": "高い類似度でマッチ..."              # 判断理由
}
```

---

## 5. トラブルシューティング

### 環境変数が設定されていない

```
エラー: FREEE_ACCESS_TOKEN が設定されていません
```

**解決方法:**

```bash
export FREEE_ACCESS_TOKEN="your_token"
export FREEE_COMPANY_ID="your_company_id"
export ANTHROPIC_API_KEY="your_api_key"
```

### APIエラーが発生する

```
API Error: 401 - Unauthorized
```

**解決方法:**
- freeeアクセストークンが有効か確認してください
- トークンの有効期限が切れていないか確認してください
- 必要なスコープ（partners）が付与されているか確認してください

### マッチング精度が低い

**解決方法:**
- `min_score` を下げて候補を増やす
- `suggest_threshold` を調整して適切な閾値を見つける
- freee取引先のショートカット1/2を適切に設定する

---

## 6. ベストプラクティス

1. **最初はドライランで実行**: `--execute` なしで結果を確認してから本番実行
2. **処理件数を制限**: `--limit` で少数から始めて精度を確認
3. **キャッシュを活用**: 同じ取引先名は2回目以降キャッシュから取得されAPI呼び出しを節約
4. **閾値の調整**: データに応じて `threshold` を調整（厳しすぎると漏れ、緩すぎると誤検出）
5. **結果のレビュー**: 自動処理後は必ず出力CSVをレビューして誤りがないか確認
