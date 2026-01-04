# freee会計 取引先情報補完システム利用マニュアル

**著者**: Manus AI
**作成日**: 2026年1月4日

## 1. システム概要

本システムは、freee会計に登録されている取引先情報のうち、クレジットカード明細などから自動登録された**店舗名や略称を含む取引先名**を、**法人番号**と**正式な会社名**で補完・整理することを目的としています。

freee会計の取引先名（例：「トイザラス熊本店」）から、店舗名などの不要な情報を自動で除去し、経済産業省の**gBizINFO API**を用いて正式な法人情報を検索します。検索結果に基づき、freeeの取引先情報を更新することで、経理処理に必要な正確な情報を整備します。

## 2. 前提条件と必要な認証情報

本システムを実行するには、freee会計とgBizINFOのAPIアクセス権限が必要です。

| 認証情報 | 取得元 | 用途 | 備考 |
| :--- | :--- | :--- | :--- |
| **freee API アクセストークン** | freee Developers Community | freee会計の取引先一覧の取得と更新 | OAuth2.0認証が必要です。有効期限にご注意ください。 |
| **freee `company_id`** | freee API | 処理対象とする事業所を特定 | freee APIの`companies`エンドポイントから取得可能です。 |
| **gBizINFO API キー** | gBizINFO（経済産業省） | 法人番号と正式名称の検索 | 事前の利用申請が必要です。 |

## 3. システムの実行方法

本システムはPythonスクリプトとして提供されます。

### 3.1. スクリプトの準備

以下のPythonスクリプト（`freee_partner_refiner.py`）を使用します。

```python
import requests
import re
import json
import os

class FreeePartnerRefiner:
    def __init__(self, freee_access_token, gbiz_api_token=None):
        self.freee_base_url = "https://api.freee.co.jp/api/1"
        self.freee_headers = {
            "Authorization": f"Bearer {freee_access_token}",
            "X-Api-Version": "2020-06-15"
        }
        self.gbiz_api_token = gbiz_api_token
        self.gbiz_base_url = "https://info.gbiz.go.jp/api/v1/hojin"

    def clean_company_name(self, name):
        """
        取引先名から不要な情報を除去し、検索用の名称を生成する。
        例: 「トイザラス熊本店」 -> 「トイザラス」
        """
        # 法人格の正規化
        name = re.sub(r'\(株\)|株式会社|（株）|有限会社|\(有\)|（有）', '', name)
        # 記号やスペースの除去を先に行う
        name = re.sub(r'[　\s\-\d]+', '', name)
        
        # 1. 明確な店舗・支店キーワードで分割
        keywords = ['店', '支店', '営業所', 'センター', 'パーキング', '駐車場', 'ショップ', 'マート', 'ストア']
        for kw in keywords:
            if kw in name:
                name = name.split(kw)[0]
                break
        
        # 2. 地名などの固有名詞が末尾に残っている場合の簡易的な除去（オプション）
        # 法人検索APIのヒット率を考慮し、ここでは地名までは削らない方針とする。
        
        return name.strip()

    def search_gbiz_info(self, keyword):
        """
        gBizINFO APIを使用して法人情報を検索する。
        """
        if not self.gbiz_api_token:
            print("gBizINFO API token is not set.")
            return None
        
        headers = {"X-Ho-Api-Key": self.gbiz_api_token}
        params = {"name": keyword, "limit": 5}
        
        try:
            response = requests.get(self.gbiz_base_url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get("hojin-infos", [])
            else:
                print(f"gBizINFO API Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error searching gBizINFO: {e}")
        return None

    def get_freee_partners(self, company_id):
        """
        freeeから取引先一覧を取得する。
        """
        params = {"company_id": company_id}
        response = requests.get(f"{self.freee_base_url}/partners", headers=self.freee_headers, params=params)
        if response.status_code == 200:
            return response.json().get("partners", [])
        else:
            print(f"Error fetching freee partners: {response.status_code} - {response.text}")
            return []

    def update_freee_partner(self, company_id, partner_id, update_data):
        """
        freeeの取引先情報を更新する。
        """
        url = f"{self.freee_base_url}/partners/{partner_id}"
        payload = {
            "company_id": company_id,
            **update_data
        }
        response = requests.put(url, headers=self.freee_headers, json=payload)
        if response.status_code == 200:
            return True
        else:
            print(f"Error updating freee partner {partner_id}: {response.status_code} - {response.text}")
            return False

    def refine_partners(self, company_id):
        """
        メイン処理: 取引先情報を取得し、補完して更新する。
        """
        partners = self.get_freee_partners(company_id)
        updated_count = 0
        
        print(f"--- freee取引先情報補完処理開始 (対象: {len(partners)}件) ---")

        for partner in partners:
            original_name = partner['name']
            partner_id = partner['id']
            current_corp_num = partner.get('corporate_number')

            # 既に法人番号が登録されている場合はスキップ
            if current_corp_num:
                continue

            search_name = self.clean_company_name(original_name)
            if not search_name:
                continue

            print(f"処理中: {original_name} -> 検索名: {search_name}")
            candidates = self.search_gbiz_info(search_name)

            if candidates:
                # 最もマッチするものを選択（簡易的に最初の1件）
                best_match = candidates[0]
                new_corp_num = best_match.get('corporate_number')
                official_name = best_match.get('name')

                # 更新データを作成
                update_data = {
                    "corporate_number": new_corp_num,
                    # 名称を「正式名称 (元の名前)」のように更新
                    "name": f"{official_name} ({original_name})"
                }
                
                # freeeの取引先情報を更新
                if self.update_freee_partner(company_id, partner_id, update_data):
                    updated_count += 1
                    print(f"  -> 更新成功: 法人番号={new_corp_num}, 新名称={update_data['name']}")
                else:
                    print(f"  -> 更新失敗: {original_name}")
            else:
                print(f"  -> gBizINFOで法人情報が見つかりませんでした: {search_name}")
        
        print(f"--- 処理完了: {updated_count}件の取引先情報を更新しました ---")
        return updated_count

# 実行例 (実際の実行にはトークンが必要です)
if __name__ == "__main__":
    # 以下のプレースホルダーを実際の値に置き換えてください
    FREE_ACCESS_TOKEN = "YOUR_FREE_ACCESS_TOKEN"
    GBIZ_API_TOKEN = "YOUR_GBIZ_API_TOKEN"
    COMPANY_ID = 1234567 # あなたのfreee事業所ID

    # 実際のAPIコールはコメントアウトしています。
    # 実行する際はコメントアウトを解除し、トークンを設定してください。
    # refiner = FreeePartnerRefiner(FREE_ACCESS_TOKEN, GBIZ_API_TOKEN)
    # refiner.refine_partners(COMPANY_ID)

    # テスト用ダミーデータでの動作確認（クレンジングロジックのみ）
    refiner = FreeePartnerRefiner("dummy_token")
    test_names = ["トイザラス熊本店", "（株）ニトリ 岡山店", "株式会社　セブンイレブン　代々木", "アマゾンジャパン", "Apple Store"]
    print("--- クレンジングロジック テスト結果 ---")
    for name in test_names:
        print(f"Original: {name} -> Cleaned: {refiner.clean_company_name(name)}")
```

### 3.2. 実行手順

1.  **認証情報の取得**: freee API アクセストークン、`company_id`、gBizINFO API キーを取得します。
2.  **スクリプトの編集**: `freee_partner_refiner.py`ファイルの末尾にある`if __name__ == "__main__":`ブロック内のプレースホルダーを、取得した実際の値に置き換えます。
3.  **実行**: 以下のコマンドでスクリプトを実行します。

    ```bash
    python3 freee_partner_refiner.py
    ```

## 4. 照合・補完ロジックの詳細

本システムの中核となるロジックは、以下のステップで構成されています。

| ステップ | 処理内容 | 目的 |
| :--- | :--- | :--- |
| **1. データ取得** | freee APIから取引先一覧を取得。法人番号が未登録の取引先を抽出。 | 処理対象の特定。 |
| **2. 名称クレンジング** | 取引先名から法人格（`（株）`など）や店舗名（`店`、`支店`など）を正規表現で除去・分割。 | gBizINFO APIでの検索ヒット率向上。 |
| **3. 外部API照合** | クレンジング後の名称でgBizINFO APIを検索し、法人番号と正式名称を取得。 | 正確な法人情報の特定。 |
| **4. データ更新** | freee APIの`partners/{id}`エンドポイントを使用し、取引先の`corporate_number`と`name`を更新。 | freee会計への情報反映。 |

### 4.1. 名称クレンジングの例

| 元の取引先名 | クレンジング後の検索名 | 処理内容 |
| :--- | :--- | :--- |
| トイザラス熊本店 | トイザラス | 「店」以降の文字列を除去。 |
| （株）ニトリ 岡山店 | ニトリ | 法人格と「店」以降の文字列を除去。スペースも除去。 |
| 株式会社　セブンイレブン　代々木 | セブンイレブン | 法人格と店舗名（代々木）を除去。全角スペースも除去。 |

## 5. 補足事項

*   **名称の更新形式**: スクリプトでは、更新後の取引先名を「**正式名称 (元の名前)**」としています。これにより、元の登録名（例：クレジットカード明細名）を残しつつ、正式名称を把握できます。この形式は、スクリプト内で自由に調整可能です。
*   **gBizINFO APIの制限**: gBizINFO APIは、検索キーワードが**前方一致**または**部分一致**で動作します。クレンジングが不十分な場合、意図しない法人がヒットする可能性があるため、必要に応じてスクリプトの`clean_company_name`関数を調整してください。
*   **実行権限**: freee APIのアクセストークンには、**取引先情報の読み取りと書き込み**の権限が必要です。

---
**References**

[1] freee Developers Community: 会計APIリファレンス. [https://developer.freee.co.jp/reference/accounting/reference]
[2] gBizINFO: API利用方法. [https://info.gbiz.go.jp/api/index.html]
