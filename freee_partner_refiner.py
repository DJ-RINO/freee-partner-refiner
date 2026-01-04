import requests
import re
import json
import os
from typing import TypedDict, NotRequired


class HojinInfo(TypedDict):
    corporate_number: str
    name: str


class Partner(TypedDict):
    id: int
    name: str
    corporate_number: NotRequired[str | None]


class RefineResult(TypedDict):
    before: str
    after: str
    corporate_number: str


class FreeePartnerRefiner:
    def __init__(self, freee_access_token: str, gbiz_api_token: str | None = None) -> None:
        self.freee_base_url: str = "https://api.freee.co.jp/api/1"
        self.freee_headers: dict[str, str] = {
            "Authorization": f"Bearer {freee_access_token}",
            "X-Api-Version": "2020-06-15"
        }
        self.gbiz_api_token: str | None = gbiz_api_token
        self.gbiz_base_url: str = "https://info.gbiz.go.jp/api/v1/hojin"

    def clean_company_name(self, name: str) -> str:
        """
        取引先名から不要な情報を除去し、検索用の名称を生成する。
        例: 「トイザラス熊本店」 -> 「トイザラス」
        """
        # 法人格の正規化
        name = re.sub(r'\(株\)|株式会社|（株）|有限会社|\(有\)|（有）', '', name)
        # 記号やスペースの除去を先に行う
        name = re.sub(r'[　\s\-\d]+', '', name)

        # 1. 明確な店舗・支店キーワードで分割
        keywords: list[str] = ['店', '支店', '営業所', 'センター', 'パーキング', '駐車場', 'ショップ', 'マート', 'ストア']
        for kw in keywords:
            if kw in name:
                name = name.split(kw)[0]
                break

        # 2. 地名などの固有名詞が末尾に残っている場合の簡易的な除去（オプション）
        # ここでは「熊本」「岡山」などの地名が残る可能性があるが、
        # 法人検索API側で「トイザラス熊本」でも「トイザラス」がヒットすることを期待するか、
        # あるいはさらに削るロジックを入れる。

        return name.strip()

    def search_gbiz_info(self, keyword: str) -> list[HojinInfo] | None:
        """
        gBizINFO APIを使用して法人情報を検索する。
        """
        if not self.gbiz_api_token:
            return None

        headers: dict[str, str] = {"X-Ho-Api-Key": self.gbiz_api_token}
        params: dict[str, str | int] = {"name": keyword, "limit": 5}

        try:
            response = requests.get(self.gbiz_base_url, headers=headers, params=params)
            if response.status_code == 200:
                data: dict = response.json()
                return data.get("hojin-infos", [])
        except Exception as e:
            print(f"Error searching gBizINFO: {e}")
        return None

    def get_freee_partners(self, company_id: int) -> list[Partner]:
        """
        freeeから取引先一覧を取得する。
        """
        params: dict[str, int] = {"company_id": company_id}
        response = requests.get(f"{self.freee_base_url}/partners", headers=self.freee_headers, params=params)
        if response.status_code == 200:
            return response.json().get("partners", [])
        else:
            print(f"Error fetching freee partners: {response.text}")
            return []

    def update_freee_partner(self, company_id: int, partner_id: int, update_data: dict[str, str]) -> bool:
        """
        freeeの取引先情報を更新する。
        """
        url: str = f"{self.freee_base_url}/partners/{partner_id}"
        payload: dict[str, str | int] = {
            "company_id": company_id,
            **update_data
        }
        response = requests.put(url, headers=self.freee_headers, json=payload)
        return response.status_code == 200

    def refine_partners(self, company_id: int) -> list[RefineResult]:
        """
        メイン処理: 取引先情報を取得し、補完して更新する。
        """
        partners: list[Partner] = self.get_freee_partners(company_id)
        results: list[RefineResult] = []

        for partner in partners:
            original_name: str = partner['name']
            current_corp_num: str | None = partner.get('corporate_number')

            # すでに法人番号がある場合はスキップ（または検証）
            if current_corp_num:
                continue

            search_name: str = self.clean_company_name(original_name)
            if not search_name:
                continue

            print(f"Searching for: {original_name} -> {search_name}")
            candidates: list[HojinInfo] | None = self.search_gbiz_info(search_name)

            if candidates:
                # 最もマッチするものを選択（簡易的に最初の1件）
                best_match: HojinInfo = candidates[0]
                new_corp_num: str = best_match.get('corporate_number', '')
                official_name: str = best_match.get('name', '')

                update_data: dict[str, str] = {
                    "corporate_number": new_corp_num,
                    # 名称を「正式名称 (元の名前)」のように更新する案
                    "name": f"{official_name} ({original_name})"
                }

                # 実際にはここで更新APIを叩く
                # self.update_freee_partner(company_id, partner['id'], update_data)
                results.append({
                    "before": original_name,
                    "after": update_data['name'],
                    "corporate_number": new_corp_num
                })

        return results

# テスト用ダミーデータでの動作確認
if __name__ == "__main__":
    # 実際のAPIキーがない状態でのロジックテスト
    refiner = FreeePartnerRefiner("dummy_token")
    test_names: list[str] = ["トイザラス熊本店", "（株）ニトリ 岡山店", "株式会社　セブンイレブン　代々木"]
    for name in test_names:
        print(f"Original: {name} -> Cleaned: {refiner.clean_company_name(name)}")
