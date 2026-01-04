# AGENTS.md - freee-partner-refiner

## プロジェクト概要

freee取引先情報をgBizINFO APIと連携して自動補完するPythonツール。

## 開発モード

**Solo モード**: Claude Code のみで開発

## ワークフロー

```
[ユーザー] → [Claude Code] → [実装・テスト・デプロイ]
```

### 基本コマンド

| コマンド | 説明 |
|---------|------|
| `/plan-with-agent` | タスクの計画を立てる |
| `/work` | Plans.md のタスクを実行 |
| `/sync-status` | 現在の状態を確認 |
| `/harness-review` | コードレビュー |

## プロジェクト構造

```
freee-partner-refiner/
├── freee_partner_refiner.py   # メインスクリプト
├── README.md                   # ドキュメント
├── .claude/                    # Claude Code 設定
│   ├── settings.json          # 権限・セーフティ設定
│   ├── memory/                # セッション記憶
│   │   ├── decisions.md       # 意思決定記録
│   │   └── patterns.md        # 再利用パターン
│   └── state/                 # 状態管理
├── AGENTS.md                   # このファイル
├── CLAUDE.md                   # Claude Code ルール
└── Plans.md                    # タスク管理
```

## 技術スタック

- **言語**: Python 3.x
- **依存ライブラリ**: requests
- **外部API**:
  - freee API（取引先管理）
  - gBizINFO API（法人情報検索）

## セーフティルール

- APIトークンは環境変数で管理（ハードコード禁止）
- 本番データの更新は確認後に実行
- 破壊的操作（rm -rf等）は禁止
