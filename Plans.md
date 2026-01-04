# Plans.md - freee-partner-refiner

## 現在のステータス

**モード**: Solo（Claude Code のみ）
**方針**: セマンティック企業マッチング

---

## ✅ フェーズ3: テスト・品質 `cc:完了`

### 完了したタスク

- [x] pytest対応（requirements.txt + pyproject.toml）
- [x] テストカバレッジ計測の設定（pytest-cov）
- [x] parent_company_finderのモックテスト（8件）
- [x] 統合テスト transaction_processor（7件）
- [x] 全41件のテスト通過

---

## ✅ 完了済みフェーズ

### フェーズ1: 基盤整備 `cc:完了`

- [x] プロジェクト初期化
- [x] ワークフローファイル作成
- [x] requirements.txt 作成
- [x] 型ヒントの追加

### フェーズ2: コア機能実装 `cc:完了`

- [x] 親会社特定モジュール → `parent_company_finder.py`
- [x] AI一括処理スクリプト → `batch_*.py`
- [x] マッチングエンジン → `partner_matcher.py`
- [x] 紐付けモジュール → `partner_linker.py`
- [x] 統合スクリプト → `transaction_processor.py`

### フェーズ3: テスト `cc:完了`

- [x] テストディレクトリ作成
- [x] partner_matcher テスト（15件）
- [x] partner_linker テスト（10件）
- [x] pytest対応 + pyproject.toml
- [x] parent_company_finder モックテスト（8件）
- [x] 統合テスト transaction_processor（7件）
- [x] **全41件通過**

---

## ✅ フェーズ4: 運用・ドキュメント `cc:完了`

### 完了したタスク

- [x] 環境変数設定ガイド（README更新）
- [x] 使用例・チュートリアル（docs/usage.md）
- [x] エラーハンドリング強化（exceptions.py）
- [x] ログ出力の追加（logger.py）

---

## 🔴 現在のフェーズ: フェーズ5（CI/CD） `cc:WIP`

### 次のタスク

- [ ] GitHub Actions 設定 `cc:TODO`
- [ ] 自動テスト `cc:TODO`
- [ ] リリースワークフロー `cc:TODO`

---

## クイックリファレンス

### コマンド

```bash
# テスト実行
python -m unittest discover -s tests -v

# 一括処理（手動ワークフロー）
python batch_processor.py manual

# 一括処理（自動・Claude API）
python batch_processor.py auto --limit 10

# 取引処理
python transaction_processor.py transactions.csv --limit 10
```

### 環境変数

```bash
export FREEE_ACCESS_TOKEN="your_token"
export FREEE_COMPANY_ID="your_company_id"
export ANTHROPIC_API_KEY="your_key"
```

---

## ハーネスワークフロー

**`/work`** を実行すると、上記の `cc:TODO` タスクを順番に処理します。

**使い方:**
- 「`/work`」→ 次のTODOタスクを実行
- 「`/sync-status`」→ 進捗を確認
- 「`/harness-review`」→ コードレビュー

---

## 完了したタスク履歴

| 日付 | タスク |
|------|--------|
| 2026-01-04 | プロジェクト初期化 |
| 2026-01-04 | 型ヒント追加 |
| 2026-01-04 | 親会社特定モジュール |
| 2026-01-04 | AI一括処理スクリプト |
| 2026-01-04 | マッチングエンジン |
| 2026-01-04 | 紐付けモジュール |
| 2026-01-04 | 統合スクリプト |
| 2026-01-04 | ユニットテスト（25件通過） |
| 2026-01-04 | マッチング＋統合テスト（全41件通過） |
| 2026-01-04 | README更新 + docs/usage.md |
| 2026-01-04 | ログ + エラーハンドリング追加 |
