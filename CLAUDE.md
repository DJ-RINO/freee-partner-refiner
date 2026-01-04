# CLAUDE.md - freee-partner-refiner

## プロジェクト概要

freee取引先情報をgBizINFO APIで補完するPythonツール。

## 開発ルール

### コーディング規約

- Python 3.x 準拠
- PEP 8 スタイルガイドに従う
- 型ヒントを使用（Python 3.9+）
- docstring は日本語でも可

### API操作

- freee API: `https://api.freee.co.jp/api/1`
- gBizINFO API: `https://info.gbiz.go.jp/api/v1/hojin`
- 認証情報は環境変数から取得:
  - `FREEE_ACCESS_TOKEN`
  - `GBIZ_API_TOKEN`

### セーフティ

- 本番更新前に必ずドライラン
- APIレート制限を考慮
- エラーハンドリングを適切に実装

## よく使うコマンド

```bash
# スクリプト実行（テスト）
python freee_partner_refiner.py

# 依存関係インストール
pip install requests

# Lint チェック
python -m py_compile freee_partner_refiner.py
```

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `freee_partner_refiner.py` | メインスクリプト |
| `README.md` | 使用方法・ドキュメント |

## 実装時の注意点

1. **名前クリーニング**: 店舗名・支店名を適切に除去
2. **法人検索**: 複数候補がある場合の選択ロジック
3. **更新処理**: 実際の更新はコメントアウト状態（安全のため）
