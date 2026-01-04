# freee Partner Refiner

銀行/カード明細の店舗名から親会社（運営法人）を特定し、freee会計の取引先とマッチングするツールです。Claude APIによる親会社特定と、セマンティックマッチングによる既存取引先への紐付けを自動化します。

## 主要機能

- **親会社特定**（Claude API）: 明細の店舗名から運営法人を特定（例: 「セブンイレブン代々木」 -> 「株式会社セブン-イレブン・ジャパン」）
- **セマンティックマッチング**: Levenshtein距離とJaro-Winkler類似度を組み合わせた高精度な企業名マッチング
- **既存freee取引先との紐付け**: 特定した親会社をfreee既存取引先と自動マッチング
- **バッチ処理対応**: CSV入力による一括処理、結果レポートの出力

## 環境変数

以下の環境変数を設定してください:

```bash
export FREEE_ACCESS_TOKEN=your_freee_access_token
export FREEE_COMPANY_ID=your_company_id
export ANTHROPIC_API_KEY=your_anthropic_api_key
```

| 環境変数 | 説明 |
|----------|------|
| `FREEE_ACCESS_TOKEN` | freee API アクセストークン（取引先の読み取り・書き込み権限が必要） |
| `FREEE_COMPANY_ID` | freee 事業所ID |
| `ANTHROPIC_API_KEY` | Anthropic（Claude）APIキー |

## インストール

```bash
# リポジトリをクローン
git clone <repository-url>
cd freee-partner-refiner

# 仮想環境を作成・有効化
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存パッケージをインストール
pip install -r requirements.txt
```

## クイックスタート

### 基本的な使用方法（transaction_processor.py）

1. 入力CSVを準備:

```csv
id,name,amount,date
1,トイザラス熊本店,5000,2026-01-01
2,セブンイレブン代々木,1200,2026-01-02
3,スターバックス新宿,800,2026-01-03
```

2. 処理を実行:

```bash
# ドライラン（最初の10件）
python transaction_processor.py transactions.csv --limit 10

# 全件処理（実際に更新を実行）
python transaction_processor.py transactions.csv --limit 0 --execute
```

### コマンドラインオプション

```
python transaction_processor.py <transactions.csv> [options]

オプション:
  --limit N       最大処理件数（デフォルト: 10、0で無制限）
  --threshold N   紐付け閾値（デフォルト: 0.6）
  --no-cache      親会社特定のキャッシュを使用しない
  --execute       実際に更新を実行（デフォルトはドライラン）
```

### バッチ処理（batch_processor.py）

```bash
# 手動ワークフロー（AI貼り付け方式）
python batch_processor.py manual

# 自動ワークフロー（Claude API使用、最初の10件）
python batch_processor.py auto --limit 10
```

## ファイル構成

```
freee-partner-refiner/
├── transaction_processor.py   # メイン処理スクリプト（推奨エントリーポイント）
├── parent_company_finder.py   # 親会社特定モジュール（Claude API）
├── partner_matcher.py         # セマンティックマッチングエンジン
├── partner_linker.py          # 取引先紐付け実行モジュール
├── batch_processor.py         # バッチ処理メインスクリプト
├── batch_export.py            # freee取引先エクスポート
├── batch_import.py            # AI結果インポート
├── requirements.txt           # 依存パッケージ
├── tests/                     # テストコード
│   ├── test_parent_company_finder.py
│   ├── test_partner_matcher.py
│   ├── test_partner_linker.py
│   └── test_transaction_processor.py
└── .cache/                    # 親会社特定のキャッシュ（自動生成）
```

### 各モジュールの役割

| ファイル | 説明 |
|----------|------|
| `transaction_processor.py` | 統合処理スクリプト。明細の読み込みから紐付け提案までを一括実行 |
| `parent_company_finder.py` | Claude APIを使用して店舗名から親会社（法人）を特定 |
| `partner_matcher.py` | Levenshtein/Jaro-Winkler距離でfreee取引先とマッチング |
| `partner_linker.py` | マッチング結果に基づき紐付け提案を生成・実行 |
| `batch_processor.py` | 手動/自動の2つのワークフローを提供 |
| `batch_export.py` | freeeから取引先一覧をCSVエクスポート |
| `batch_import.py` | AI処理結果をfreeeにインポート |

## テスト実行

```bash
# 全テストを実行
pytest

# カバレッジ付きで実行
pytest --cov=. --cov-report=html

# 特定のテストファイルを実行
pytest tests/test_partner_matcher.py -v
```

## 処理フロー

```
1. 明細CSV読み込み
   ↓
2. 親会社特定（Claude API）
   例: "トイザラス熊本店" -> "日本トイザらス株式会社"
   ↓
3. freee取引先とマッチング
   - 法人番号での完全一致
   - 名前の類似度検索（Levenshtein + Jaro-Winkler）
   ↓
4. 紐付け提案を生成
   - link: 既存取引先に紐付け
   - create: 新規取引先を作成
   - skip: 判断できない
   ↓
5. 結果をCSVエクスポート
```

## ライセンス

MIT License
