# Plans.md - freee-partner-refiner

## 現在のステータス

**モード**: Solo（Claude Code のみ）
**方針**: セマンティック企業マッチング（2026-01-04決定）

---

## ✅ AI一括処理 `cc:完了`

### 実装済みスクリプト

| ファイル | 説明 |
|---------|------|
| `batch_export.py` | freee取引先をCSVエクスポート |
| `batch_import.py` | AI結果をfreeeにインポート |
| `batch_processor.py` | 一括処理メインスクリプト |
| `prompts/batch_lookup_prompt.md` | AI用プロンプトテンプレート |

### 使い方

#### 方法1: 手動ワークフロー（Manus/ChatGPT使用）

```bash
# Step 1: 環境変数設定
export FREEE_ACCESS_TOKEN="your_token"
export FREEE_COMPANY_ID="your_company_id"

# Step 2: 手動ワークフロー実行
python batch_processor.py manual
```

#### 方法2: 自動ワークフロー（Claude API使用）

```bash
# 環境変数に ANTHROPIC_API_KEY も追加
export ANTHROPIC_API_KEY="your_key"

# 最初の10件をテスト
python batch_processor.py auto --limit 10
```

---

## アーキテクチャ概要

```
銀行/カード明細 "トイザラス熊本店"
        ↓
[Step 1] 親会社特定（Web検索 + AI解析）
        ↓
     "株式会社トイザラス"
        ↓
[Step 2] freee既存取引先を取得
        ↓
[Step 3] 類似度マッチング
        ↓
[Step 4] 紐付け提案 or 新規作成提案
```

---

## フェーズ1: 基盤整備 `cc:完了`

- [x] プロジェクト初期化
- [x] ワークフローファイル作成
- [x] requirements.txt 作成
- [x] 型ヒントの追加

## フェーズ2: 新アーキテクチャ実装 `cc:WIP`

### Step 1: 親会社特定モジュール
- [ ] Web検索クライアント実装（Google/Bing API or スクレイピング）
- [ ] AI解析モジュール（Claude API で親会社名を抽出）
- [ ] キャッシュ機構（同じ店舗名の再検索を防ぐ）

### Step 2: freee既存取引先連携
- [x] 取引先一覧取得（既存）
- [ ] 取引先データのインデックス化（高速検索用）

### Step 3: マッチングエンジン
- [ ] 類似度計算（レーベンシュタイン距離 / Jaro-Winkler）
- [ ] 法人番号での完全一致チェック
- [ ] 閾値設定と候補ランキング

### Step 4: 結果出力・紐付け
- [ ] マッチ結果のレポート生成
- [ ] freee取引先への紐付けAPI呼び出し
- [ ] 新規取引先作成提案（gBizINFO連携）

## フェーズ3: テスト・品質 `cc:TODO`

- [ ] ユニットテスト作成
- [ ] 実データでの検証（サンプル10件）
- [ ] エッジケース対応（個人事業主、海外企業など）

## フェーズ4: 運用・ドキュメント `cc:TODO`

- [ ] 環境変数設定ガイド
- [ ] 使用例・チュートリアル
- [ ] エラーハンドリング強化

---

## 必要なAPI/サービス

| サービス | 用途 | 必須/任意 |
|---------|------|----------|
| freee API | 取引先管理 | 必須 |
| Claude API | 親会社名の解析 | 必須 |
| gBizINFO API | 法人番号取得 | 必須 |
| Google Search API | Web検索 | 任意（代替あり）|

---

## 次にやること

「**続けて**」→ フェーズ2の実装を開始
「**Step 1から**」→ 親会社特定モジュールから実装

---

## 完了したタスク

| 日付 | タスク | 備考 |
|------|--------|------|
| 2026-01-04 | プロジェクト初期化 | harness-init |
| 2026-01-04 | ワークフローファイル作成 | AGENTS.md, CLAUDE.md, Plans.md |
| 2026-01-04 | requirements.txt | requests>=2.28.0, anthropic>=0.40.0 |
| 2026-01-04 | 型ヒント追加 | TypedDict, Python 3.10+ |
| 2026-01-04 | アーキテクチャ変更決定 | セマンティック企業マッチング方式 |
| 2026-01-04 | 親会社特定モジュール | parent_company_finder.py |
| 2026-01-04 | AI一括処理スクリプト | batch_export/import/processor.py |
| 2026-01-04 | プロンプトテンプレート | prompts/batch_lookup_prompt.md |
