"""
一括処理メインスクリプト

freee取引先の法人情報を一括で補完する。
手動（AI貼り付け）と自動（Claude API）の両方に対応。
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path

from batch_export import FreeePartnerExporter
from batch_import import FreeePartnerImporter, ImportConfig
from parent_company_finder import ParentCompanyFinder


def print_header(title: str) -> None:
    """ヘッダーを表示"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def manual_workflow(company_id: int) -> None:
    """
    手動ワークフロー（AI貼り付け方式）

    1. freeeからエクスポート
    2. ユーザーがAIに投入
    3. 結果をインポート
    """
    print_header("手動ワークフロー（AI貼り付け方式）")

    # Step 1: エクスポート
    print("\n📤 Step 1: freeeから取引先をエクスポート")
    exporter = FreeePartnerExporter()
    export_path = exporter.export_for_ai(company_id)

    # Step 2: AIに投入（手動）
    print("\n📝 Step 2: AIに投入してください")
    print("-" * 40)
    print("1. prompts/batch_lookup_prompt.md を開く")
    print("2. プロンプトをコピーしてAI（Manus/ChatGPT/Claude）に貼り付け")
    print(f"3. {export_path} の内容を貼り付け")
    print("4. AIの出力を ai_result.csv として保存")
    print("-" * 40)

    # Step 3: 結果をインポート
    input("\n準備ができたらEnterキーを押してください...")

    result_path = input("結果ファイルのパス (デフォルト: ai_result.csv): ").strip()
    if not result_path:
        result_path = "ai_result.csv"

    if not Path(result_path).exists():
        print(f"❌ ファイルが見つかりません: {result_path}")
        return

    print(f"\n📥 Step 3: 結果をインポート（ドライラン）")
    importer = FreeePartnerImporter()
    config = ImportConfig(dry_run=True)
    results = importer.import_results(company_id, result_path, config)

    # 確認
    execute = input("\n実際に更新を実行しますか？ (yes/no): ").strip().lower()
    if execute == "yes":
        print("\n📥 実行中...")
        config = ImportConfig(dry_run=False)
        results = importer.import_results(company_id, result_path, config)
        importer.export_update_report(results)
        print("\n✅ 完了！")
    else:
        print("\nキャンセルしました")


def auto_workflow(company_id: int, limit: int = 10) -> None:
    """
    自動ワークフロー（Claude API使用）

    Claude APIを使って自動的に法人情報を調査・更新する。
    """
    print_header("自動ワークフロー（Claude API使用）")

    # 環境変数チェック
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY が設定されていません")
        return

    # Step 1: freeeから取引先を取得
    print("\n📤 Step 1: freeeから取引先を取得")
    exporter = FreeePartnerExporter()
    partners = exporter.get_partners(company_id)

    # 法人番号がない取引先のみ
    partners_to_process = [p for p in partners if not p["corporate_number"]]
    print(f"   対象: {len(partners_to_process)}件（法人番号未設定）")

    if limit > 0:
        partners_to_process = partners_to_process[:limit]
        print(f"   処理制限: {limit}件")

    if not partners_to_process:
        print("   処理対象がありません")
        return

    # Step 2: Claude APIで親会社を特定
    print("\n🔍 Step 2: Claude APIで法人情報を調査")
    finder = ParentCompanyFinder()

    results = []
    for i, partner in enumerate(partners_to_process, 1):
        print(f"   [{i}/{len(partners_to_process)}] {partner['name']}")

        result = finder.find_parent_company(partner["name"])
        results.append({
            "id": partner["id"],
            "original_name": partner["name"],
            "official_name": result["parent_company"],
            "confidence": result["confidence"],
            "is_individual": result["is_individual"],
            "notes": result["notes"]
        })

        if result["parent_company"]:
            print(f"       → {result['parent_company']} ({result['confidence']})")
        else:
            print(f"       → 特定できず ({result['confidence']})")

    # Step 3: 結果を表示
    print_header("調査結果")

    high_confidence = [r for r in results if r["confidence"] == "high"]
    medium_confidence = [r for r in results if r["confidence"] == "medium"]
    low_confidence = [r for r in results if r["confidence"] in ["low", "unknown"]]

    print(f"\n📊 確信度別の件数")
    print(f"   🟢 high: {len(high_confidence)}件")
    print(f"   🟡 medium: {len(medium_confidence)}件")
    print(f"   🔴 low/unknown: {len(low_confidence)}件")

    # CSV出力
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"auto_result_{timestamp}.csv"

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "取引先名", "正式法人名", "法人番号",
            "インボイス登録番号", "確信度", "備考"
        ])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "id": r["id"],
                "取引先名": r["original_name"],
                "正式法人名": r["official_name"] or "",
                "法人番号": "",  # gBizINFOで別途取得が必要
                "インボイス登録番号": "",
                "確信度": r["confidence"],
                "備考": f"{'個人事業主の可能性' if r['is_individual'] else ''}{r['notes']}"
            })

    print(f"\n📄 結果出力: {output_path}")
    print("\n⚠️  注意: 法人番号は gBizINFO API で別途取得が必要です")
    print("   → このファイルを編集して法人番号を追加後、batch_import.py でインポート")


def show_usage() -> None:
    """使用方法を表示"""
    print("""
freee取引先一括処理ツール

使用方法:
  python batch_processor.py <mode> [options]

モード:
  manual    手動ワークフロー（AI貼り付け方式）
  auto      自動ワークフロー（Claude API使用）

環境変数:
  FREEE_ACCESS_TOKEN   freee APIアクセストークン（必須）
  FREEE_COMPANY_ID     freee事業所ID（必須）
  ANTHROPIC_API_KEY    Claude APIキー（autoモードで必須）

例:
  # 手動ワークフロー
  python batch_processor.py manual

  # 自動ワークフロー（最初の10件のみ）
  python batch_processor.py auto --limit 10

  # 自動ワークフロー（全件）
  python batch_processor.py auto --limit 0
""")


def main() -> None:
    """メイン処理"""
    if len(sys.argv) < 2:
        show_usage()
        sys.exit(1)

    mode = sys.argv[1]

    # 環境変数チェック
    if not os.environ.get("FREEE_ACCESS_TOKEN"):
        print("❌ FREEE_ACCESS_TOKEN が設定されていません")
        sys.exit(1)

    company_id = int(os.environ.get("FREEE_COMPANY_ID", "0"))
    if company_id == 0:
        print("❌ FREEE_COMPANY_ID が設定されていません")
        sys.exit(1)

    if mode == "manual":
        manual_workflow(company_id)
    elif mode == "auto":
        limit = 10  # デフォルト
        if "--limit" in sys.argv:
            idx = sys.argv.index("--limit")
            if idx + 1 < len(sys.argv):
                limit = int(sys.argv[idx + 1])
        auto_workflow(company_id, limit)
    else:
        print(f"❌ 不明なモード: {mode}")
        show_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
