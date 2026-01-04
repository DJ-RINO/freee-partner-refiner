"""
AI処理結果インポートスクリプト

AIが出力したCSVをfreee形式に変換し、取引先情報を更新する。
"""

import csv
import os
import requests
from dataclasses import dataclass
from typing import TypedDict


class AIResult(TypedDict):
    """AIの出力結果"""
    id: int
    original_name: str
    official_name: str | None
    corporate_number: str | None
    invoice_number: str | None
    confidence: str
    notes: str


class UpdateResult(TypedDict):
    """更新結果"""
    id: int
    name: str
    status: str  # success, skipped, error
    message: str


@dataclass
class ImportConfig:
    """インポート設定"""
    dry_run: bool = True  # True: 実際には更新しない
    skip_low_confidence: bool = True  # low/unknownの確信度をスキップ
    update_name: bool = False  # 取引先名も更新するか
    backup: bool = True  # 更新前にバックアップを作成


class FreeePartnerImporter:
    """AI結果をfreeeにインポートするクラス"""

    def __init__(self, access_token: str | None = None) -> None:
        """
        初期化

        Args:
            access_token: freee APIアクセストークン（省略時は環境変数から取得）
        """
        self.access_token = access_token or os.environ.get("FREEE_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError("FREEE_ACCESS_TOKEN が設定されていません")

        self.base_url = "https://api.freee.co.jp/api/1"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Api-Version": "2020-06-15",
            "Content-Type": "application/json"
        }

    def parse_ai_csv(self, csv_path: str) -> list[AIResult]:
        """
        AIが出力したCSVをパース

        Args:
            csv_path: CSVファイルパス

        Returns:
            AIResultのリスト
        """
        results: list[AIResult] = []

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # カラム名の正規化（日本語/英語両対応）
                result: AIResult = {
                    "id": int(row.get("id", 0)),
                    "original_name": row.get("取引先名", row.get("original_name", "")),
                    "official_name": row.get("正式法人名", row.get("official_name")) or None,
                    "corporate_number": self._normalize_corp_number(
                        row.get("法人番号", row.get("corporate_number"))
                    ),
                    "invoice_number": row.get("インボイス登録番号", row.get("invoice_number")) or None,
                    "confidence": row.get("確信度", row.get("confidence", "unknown")),
                    "notes": row.get("備考", row.get("notes", ""))
                }
                results.append(result)

        return results

    def _normalize_corp_number(self, value: str | None) -> str | None:
        """法人番号を正規化（13桁の数字のみ）"""
        if not value:
            return None
        # 数字のみ抽出
        digits = "".join(c for c in str(value) if c.isdigit())
        if len(digits) == 13:
            return digits
        return None

    def validate_results(self, results: list[AIResult]) -> tuple[list[AIResult], list[AIResult]]:
        """
        結果を検証し、有効/無効に分類

        Args:
            results: AIResultのリスト

        Returns:
            (有効なリスト, 無効なリスト)
        """
        valid: list[AIResult] = []
        invalid: list[AIResult] = []

        for r in results:
            if not r["id"]:
                invalid.append(r)
                continue
            if not r["corporate_number"]:
                invalid.append(r)
                continue
            if r["confidence"] in ["low", "unknown"]:
                invalid.append(r)
                continue
            valid.append(r)

        return valid, invalid

    def update_partner(
        self,
        company_id: int,
        partner_id: int,
        corporate_number: str,
        invoice_number: str | None = None,
        name: str | None = None
    ) -> bool:
        """
        freeeの取引先を更新

        Args:
            company_id: 事業所ID
            partner_id: 取引先ID
            corporate_number: 法人番号
            invoice_number: インボイス登録番号
            name: 更新する名前（省略時は更新しない）

        Returns:
            成功したかどうか
        """
        url = f"{self.base_url}/partners/{partner_id}"

        payload: dict = {
            "company_id": company_id,
            "corporate_number": corporate_number
        }

        if invoice_number:
            payload["invoice_registration_number"] = invoice_number

        if name:
            payload["name"] = name

        response = requests.put(url, headers=self.headers, json=payload)
        return response.status_code == 200

    def import_results(
        self,
        company_id: int,
        csv_path: str,
        config: ImportConfig | None = None
    ) -> list[UpdateResult]:
        """
        AI結果をfreeeにインポート

        Args:
            company_id: 事業所ID
            csv_path: AI結果のCSVパス
            config: インポート設定

        Returns:
            更新結果のリスト
        """
        if config is None:
            config = ImportConfig()

        results = self.parse_ai_csv(csv_path)
        valid, invalid = self.validate_results(results)

        update_results: list[UpdateResult] = []

        # 無効な結果をスキップとして記録
        for r in invalid:
            update_results.append({
                "id": r["id"],
                "name": r["original_name"],
                "status": "skipped",
                "message": f"確信度: {r['confidence']}, 法人番号: {r['corporate_number'] or 'なし'}"
            })

        # 有効な結果を処理
        print(f"\n📊 処理対象: {len(valid)}件 / 全{len(results)}件")
        print(f"   スキップ: {len(invalid)}件（確信度低/法人番号なし）")

        if config.dry_run:
            print("\n⚠️  ドライランモード（実際には更新しません）")

        for r in valid:
            if config.dry_run:
                # ドライラン: 更新内容を表示するのみ
                print(f"\n[DRY RUN] ID={r['id']}")
                print(f"  取引先名: {r['original_name']}")
                print(f"  → 法人番号: {r['corporate_number']}")
                if r["invoice_number"]:
                    print(f"  → インボイス: {r['invoice_number']}")
                if r["official_name"] and config.update_name:
                    print(f"  → 正式名称: {r['official_name']}")

                update_results.append({
                    "id": r["id"],
                    "name": r["original_name"],
                    "status": "success",
                    "message": "ドライラン完了"
                })
            else:
                # 実際に更新
                try:
                    name_to_update = r["official_name"] if config.update_name else None
                    success = self.update_partner(
                        company_id=company_id,
                        partner_id=r["id"],
                        corporate_number=r["corporate_number"],
                        invoice_number=r["invoice_number"],
                        name=name_to_update
                    )

                    if success:
                        update_results.append({
                            "id": r["id"],
                            "name": r["original_name"],
                            "status": "success",
                            "message": f"法人番号: {r['corporate_number']}"
                        })
                        print(f"✅ 更新成功: {r['original_name']}")
                    else:
                        update_results.append({
                            "id": r["id"],
                            "name": r["original_name"],
                            "status": "error",
                            "message": "API更新失敗"
                        })
                        print(f"❌ 更新失敗: {r['original_name']}")

                except Exception as e:
                    update_results.append({
                        "id": r["id"],
                        "name": r["original_name"],
                        "status": "error",
                        "message": str(e)
                    })
                    print(f"❌ エラー: {r['original_name']} - {e}")

        # サマリー出力
        success_count = sum(1 for r in update_results if r["status"] == "success")
        skip_count = sum(1 for r in update_results if r["status"] == "skipped")
        error_count = sum(1 for r in update_results if r["status"] == "error")

        print(f"\n📊 結果サマリー")
        print(f"   ✅ 成功: {success_count}件")
        print(f"   ⏭️  スキップ: {skip_count}件")
        print(f"   ❌ エラー: {error_count}件")

        return update_results

    def export_update_report(
        self,
        results: list[UpdateResult],
        output_path: str = "import_report.csv"
    ) -> str:
        """
        更新結果レポートを出力

        Args:
            results: 更新結果リスト
            output_path: 出力パス

        Returns:
            出力ファイルパス
        """
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "name", "status", "message"])
            writer.writeheader()
            writer.writerows(results)

        print(f"\n📄 レポート出力: {output_path}")
        return output_path


# テスト/実行用
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("使用方法: python batch_import.py <ai_result.csv> [--execute]")
        print("")
        print("オプション:")
        print("  --execute  実際に更新を実行（デフォルトはドライラン）")
        sys.exit(1)

    csv_path = sys.argv[1]
    dry_run = "--execute" not in sys.argv

    try:
        importer = FreeePartnerImporter()
        company_id = int(os.environ.get("FREEE_COMPANY_ID", "0"))

        if company_id == 0:
            print("FREEE_COMPANY_ID を設定してください")
            sys.exit(1)

        config = ImportConfig(dry_run=dry_run)
        results = importer.import_results(company_id, csv_path, config)
        importer.export_update_report(results)

    except ValueError as e:
        print(f"エラー: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"ファイルが見つかりません: {csv_path}")
        sys.exit(1)
