"""
freee取引先エクスポートスクリプト

freeeから取引先一覧を取得し、AI処理用のCSV形式でエクスポートする。
"""

import csv
import os
import requests
from datetime import datetime
from typing import TypedDict


class PartnerExport(TypedDict):
    """エクスポートする取引先データ"""
    id: int
    name: str
    shortcut1: str | None
    shortcut2: str | None
    long_name: str | None
    corporate_number: str | None
    invoice_registration_number: str | None
    address: str | None


class FreeePartnerExporter:
    """freee取引先をCSVにエクスポートするクラス"""

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
            "X-Api-Version": "2020-06-15"
        }

    def get_partners(self, company_id: int) -> list[PartnerExport]:
        """
        freeeから取引先一覧を取得

        Args:
            company_id: freee事業所ID

        Returns:
            取引先リスト
        """
        partners: list[PartnerExport] = []
        offset = 0
        limit = 100

        while True:
            params = {
                "company_id": company_id,
                "offset": offset,
                "limit": limit
            }

            response = requests.get(
                f"{self.base_url}/partners",
                headers=self.headers,
                params=params
            )

            if response.status_code != 200:
                raise Exception(f"API Error: {response.status_code} - {response.text}")

            data = response.json()
            batch = data.get("partners", [])

            if not batch:
                break

            for p in batch:
                partners.append({
                    "id": p["id"],
                    "name": p["name"],
                    "shortcut1": p.get("shortcut1"),
                    "shortcut2": p.get("shortcut2"),
                    "long_name": p.get("long_name"),
                    "corporate_number": p.get("corporate_number"),
                    "invoice_registration_number": p.get("invoice_registration_number"),
                    "address": self._format_address(p)
                })

            offset += limit

            # 取得件数がlimitより少なければ終了
            if len(batch) < limit:
                break

        return partners

    def _format_address(self, partner: dict) -> str | None:
        """住所をフォーマット"""
        parts = []
        if partner.get("pref_code"):
            # 都道府県コードを名前に変換（簡易版）
            pref_names = {
                1: "北海道", 13: "東京都", 14: "神奈川県", 23: "愛知県",
                26: "京都府", 27: "大阪府", 28: "兵庫県", 40: "福岡県"
                # 必要に応じて追加
            }
            pref = pref_names.get(partner["pref_code"], f"都道府県{partner['pref_code']}")
            parts.append(pref)
        if partner.get("address1"):
            parts.append(partner["address1"])
        if partner.get("address2"):
            parts.append(partner["address2"])
        return " ".join(parts) if parts else None

    def export_to_csv(
        self,
        company_id: int,
        output_path: str | None = None,
        include_with_corporate_number: bool = False
    ) -> str:
        """
        取引先をCSVにエクスポート

        Args:
            company_id: freee事業所ID
            output_path: 出力ファイルパス（省略時は自動生成）
            include_with_corporate_number: 法人番号がある取引先も含めるか

        Returns:
            出力ファイルパス
        """
        partners = self.get_partners(company_id)

        # フィルタリング
        if not include_with_corporate_number:
            partners = [p for p in partners if not p["corporate_number"]]

        # 出力パス
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"freee_partners_export_{timestamp}.csv"

        # CSV出力
        fieldnames = [
            "id", "name", "shortcut1", "shortcut2", "long_name",
            "corporate_number", "invoice_registration_number", "address"
        ]

        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(partners)

        print(f"✅ エクスポート完了: {output_path}")
        print(f"   取引先数: {len(partners)}件")
        if not include_with_corporate_number:
            print(f"   (法人番号未設定の取引先のみ)")

        return output_path

    def export_for_ai(
        self,
        company_id: int,
        output_path: str | None = None
    ) -> str:
        """
        AI処理用にシンプルな形式でエクスポート

        Args:
            company_id: freee事業所ID
            output_path: 出力ファイルパス

        Returns:
            出力ファイルパス
        """
        partners = self.get_partners(company_id)

        # 法人番号がない取引先のみ
        partners = [p for p in partners if not p["corporate_number"]]

        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"freee_partners_for_ai_{timestamp}.csv"

        # AI処理用のシンプルなCSV
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "取引先名", "住所（参考）"])
            for p in partners:
                writer.writerow([p["id"], p["name"], p["address"] or ""])

        print(f"✅ AI用エクスポート完了: {output_path}")
        print(f"   取引先数: {len(partners)}件（法人番号未設定のみ）")

        return output_path


# テスト用
if __name__ == "__main__":
    try:
        exporter = FreeePartnerExporter()
        # company_id は環境変数または引数で指定
        company_id = int(os.environ.get("FREEE_COMPANY_ID", "0"))
        if company_id == 0:
            print("FREEE_COMPANY_ID を設定してください")
        else:
            exporter.export_for_ai(company_id)
    except ValueError as e:
        print(f"エラー: {e}")
