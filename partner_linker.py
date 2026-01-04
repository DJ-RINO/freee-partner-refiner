"""
取引先紐付けモジュール

マッチング結果を元に、freee取引先への紐付けを実行する。
"""

import csv
import os
import requests
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypedDict

from partner_matcher import MatchCandidate, PartnerData


class LinkProposal(TypedDict):
    """紐付け提案"""
    transaction_name: str        # 明細の取引先名
    parent_company: str | None   # 特定された親会社名
    corporate_number: str | None # 法人番号
    action: str                  # link, create, skip
    target_partner: PartnerData | None  # 紐付け先（linkの場合）
    match_score: float           # マッチスコア
    confidence: str              # high, medium, low
    reason: str                  # 判断理由


class LinkResult(TypedDict):
    """紐付け結果"""
    transaction_name: str
    action: str
    status: str  # success, failed, skipped
    message: str
    partner_id: int | None


@dataclass
class LinkConfig:
    """紐付け設定"""
    auto_link_threshold: float = 0.9    # 自動紐付けの閾値
    suggest_threshold: float = 0.6      # 提案表示の閾値
    create_new_if_no_match: bool = True # マッチなしの場合に新規作成を提案
    dry_run: bool = True                # ドライラン（実際には更新しない）


class PartnerLinker:
    """
    取引先紐付け実行クラス

    マッチング結果を元に、以下のアクションを提案・実行する:
    - link: 既存取引先に紐付け
    - create: 新規取引先を作成
    - skip: スキップ（判断できない）
    """

    def __init__(
        self,
        access_token: str | None = None,
        config: LinkConfig | None = None
    ) -> None:
        """
        初期化

        Args:
            access_token: freee APIアクセストークン
            config: 紐付け設定
        """
        self.access_token = access_token or os.environ.get("FREEE_ACCESS_TOKEN")
        self.config = config or LinkConfig()

        if self.access_token:
            self.base_url = "https://api.freee.co.jp/api/1"
            self.headers = {
                "Authorization": f"Bearer {self.access_token}",
                "X-Api-Version": "2020-06-15",
                "Content-Type": "application/json"
            }
        else:
            self.base_url = None
            self.headers = {}

    def create_proposal(
        self,
        transaction_name: str,
        parent_company: str | None,
        corporate_number: str | None,
        candidates: list[MatchCandidate]
    ) -> LinkProposal:
        """
        紐付け提案を作成

        Args:
            transaction_name: 明細の取引先名
            parent_company: 特定された親会社名
            corporate_number: 法人番号
            candidates: マッチング候補

        Returns:
            紐付け提案
        """
        if not parent_company:
            return {
                "transaction_name": transaction_name,
                "parent_company": None,
                "corporate_number": None,
                "action": "skip",
                "target_partner": None,
                "match_score": 0.0,
                "confidence": "unknown",
                "reason": "親会社を特定できませんでした"
            }

        if not candidates:
            # マッチなし → 新規作成を提案
            if self.config.create_new_if_no_match:
                return {
                    "transaction_name": transaction_name,
                    "parent_company": parent_company,
                    "corporate_number": corporate_number,
                    "action": "create",
                    "target_partner": None,
                    "match_score": 0.0,
                    "confidence": "medium" if corporate_number else "low",
                    "reason": f"既存取引先にマッチなし。新規作成を推奨: {parent_company}"
                }
            else:
                return {
                    "transaction_name": transaction_name,
                    "parent_company": parent_company,
                    "corporate_number": corporate_number,
                    "action": "skip",
                    "target_partner": None,
                    "match_score": 0.0,
                    "confidence": "low",
                    "reason": "既存取引先にマッチなし"
                }

        # 最良候補を評価
        best = candidates[0]
        score = best["score"]

        if score >= self.config.auto_link_threshold:
            # 高スコア → 自動紐付け
            return {
                "transaction_name": transaction_name,
                "parent_company": parent_company,
                "corporate_number": corporate_number,
                "action": "link",
                "target_partner": best["partner"],
                "match_score": score,
                "confidence": "high",
                "reason": f"高い類似度でマッチ: {best['partner']['name']} (スコア: {score:.2f})"
            }
        elif score >= self.config.suggest_threshold:
            # 中スコア → 提案（確認が必要）
            return {
                "transaction_name": transaction_name,
                "parent_company": parent_company,
                "corporate_number": corporate_number,
                "action": "link",
                "target_partner": best["partner"],
                "match_score": score,
                "confidence": "medium",
                "reason": f"候補あり（要確認）: {best['partner']['name']} (スコア: {score:.2f})"
            }
        else:
            # 低スコア → 新規作成を提案
            if self.config.create_new_if_no_match:
                return {
                    "transaction_name": transaction_name,
                    "parent_company": parent_company,
                    "corporate_number": corporate_number,
                    "action": "create",
                    "target_partner": None,
                    "match_score": score,
                    "confidence": "low",
                    "reason": f"マッチ候補のスコアが低い ({score:.2f})。新規作成を推奨"
                }
            else:
                return {
                    "transaction_name": transaction_name,
                    "parent_company": parent_company,
                    "corporate_number": corporate_number,
                    "action": "skip",
                    "target_partner": None,
                    "match_score": score,
                    "confidence": "low",
                    "reason": f"マッチ候補のスコアが低い ({score:.2f})"
                }

    def execute_link(
        self,
        company_id: int,
        proposal: LinkProposal
    ) -> LinkResult:
        """
        紐付けを実行

        Args:
            company_id: 事業所ID
            proposal: 紐付け提案

        Returns:
            実行結果
        """
        if self.config.dry_run:
            return {
                "transaction_name": proposal["transaction_name"],
                "action": proposal["action"],
                "status": "skipped",
                "message": "[DRY RUN] 実行されませんでした",
                "partner_id": proposal["target_partner"]["id"] if proposal["target_partner"] else None
            }

        if proposal["action"] == "skip":
            return {
                "transaction_name": proposal["transaction_name"],
                "action": "skip",
                "status": "skipped",
                "message": proposal["reason"],
                "partner_id": None
            }

        if proposal["action"] == "link":
            # 既存取引先への紐付け
            # 注: 実際の紐付けはfreeeの取引登録時に行うため、
            #     ここでは取引先IDを返すのみ
            partner = proposal["target_partner"]
            if partner:
                return {
                    "transaction_name": proposal["transaction_name"],
                    "action": "link",
                    "status": "success",
                    "message": f"取引先 '{partner['name']}' に紐付け",
                    "partner_id": partner["id"]
                }

        if proposal["action"] == "create":
            # 新規取引先を作成
            if not self.access_token:
                return {
                    "transaction_name": proposal["transaction_name"],
                    "action": "create",
                    "status": "failed",
                    "message": "APIトークンが設定されていません",
                    "partner_id": None
                }

            try:
                new_partner = self._create_partner(
                    company_id=company_id,
                    name=proposal["parent_company"] or proposal["transaction_name"],
                    corporate_number=proposal["corporate_number"]
                )
                if new_partner:
                    return {
                        "transaction_name": proposal["transaction_name"],
                        "action": "create",
                        "status": "success",
                        "message": f"新規取引先を作成: {new_partner['name']}",
                        "partner_id": new_partner["id"]
                    }
            except Exception as e:
                return {
                    "transaction_name": proposal["transaction_name"],
                    "action": "create",
                    "status": "failed",
                    "message": f"作成失敗: {e}",
                    "partner_id": None
                }

        return {
            "transaction_name": proposal["transaction_name"],
            "action": proposal["action"],
            "status": "failed",
            "message": "不明なアクション",
            "partner_id": None
        }

    def _create_partner(
        self,
        company_id: int,
        name: str,
        corporate_number: str | None = None
    ) -> dict | None:
        """freeeに新規取引先を作成"""
        if not self.base_url:
            return None

        payload = {
            "company_id": company_id,
            "name": name
        }

        if corporate_number:
            payload["corporate_number"] = corporate_number
            # インボイス登録番号も設定
            payload["invoice_registration_number"] = f"T{corporate_number}"

        response = requests.post(
            f"{self.base_url}/partners",
            headers=self.headers,
            json=payload
        )

        if response.status_code in [200, 201]:
            return response.json().get("partner")
        else:
            raise Exception(f"API Error: {response.status_code} - {response.text}")


class LinkReportGenerator:
    """紐付けレポート生成"""

    def __init__(self) -> None:
        self.proposals: list[LinkProposal] = []
        self.results: list[LinkResult] = []

    def add_proposal(self, proposal: LinkProposal) -> None:
        """提案を追加"""
        self.proposals.append(proposal)

    def add_result(self, result: LinkResult) -> None:
        """結果を追加"""
        self.results.append(result)

    def generate_proposal_report(self, output_path: str | None = None) -> str:
        """提案レポートを生成"""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"link_proposals_{timestamp}.csv"

        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "取引先名（明細）",
                "親会社名",
                "法人番号",
                "アクション",
                "紐付け先",
                "スコア",
                "確信度",
                "理由"
            ])

            for p in self.proposals:
                target_name = p["target_partner"]["name"] if p["target_partner"] else ""
                writer.writerow([
                    p["transaction_name"],
                    p["parent_company"] or "",
                    p["corporate_number"] or "",
                    p["action"],
                    target_name,
                    f"{p['match_score']:.2f}",
                    p["confidence"],
                    p["reason"]
                ])

        return output_path

    def generate_result_report(self, output_path: str | None = None) -> str:
        """結果レポートを生成"""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"link_results_{timestamp}.csv"

        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "取引先名",
                "アクション",
                "ステータス",
                "メッセージ",
                "パートナーID"
            ])

            for r in self.results:
                writer.writerow([
                    r["transaction_name"],
                    r["action"],
                    r["status"],
                    r["message"],
                    r["partner_id"] or ""
                ])

        return output_path

    def print_summary(self) -> None:
        """サマリーを表示"""
        # 提案サマリー
        if self.proposals:
            actions = {}
            confidences = {}
            for p in self.proposals:
                actions[p["action"]] = actions.get(p["action"], 0) + 1
                confidences[p["confidence"]] = confidences.get(p["confidence"], 0) + 1

            print("\n📊 提案サマリー")
            print(f"   合計: {len(self.proposals)}件")
            print(f"   アクション別:")
            for action, count in actions.items():
                icon = {"link": "🔗", "create": "➕", "skip": "⏭️"}.get(action, "❓")
                print(f"      {icon} {action}: {count}件")
            print(f"   確信度別:")
            for conf, count in confidences.items():
                icon = {"high": "🟢", "medium": "🟡", "low": "🔴", "unknown": "⚪"}.get(conf, "❓")
                print(f"      {icon} {conf}: {count}件")

        # 結果サマリー
        if self.results:
            statuses = {}
            for r in self.results:
                statuses[r["status"]] = statuses.get(r["status"], 0) + 1

            print("\n📊 実行結果サマリー")
            print(f"   合計: {len(self.results)}件")
            for status, count in statuses.items():
                icon = {"success": "✅", "failed": "❌", "skipped": "⏭️"}.get(status, "❓")
                print(f"      {icon} {status}: {count}件")


# テスト用
if __name__ == "__main__":
    from partner_matcher import PartnerMatcher, PartnerData

    # テストデータ
    test_partners: list[PartnerData] = [
        {
            "id": 1,
            "name": "株式会社セブン-イレブン・ジャパン",
            "shortcut1": "セブンイレブン",
            "shortcut2": None,
            "long_name": None,
            "corporate_number": "8011101021428"
        },
        {
            "id": 2,
            "name": "日本トイザらス株式会社",
            "shortcut1": "トイザらス",
            "shortcut2": None,
            "long_name": None,
            "corporate_number": "4010401089234"
        }
    ]

    matcher = PartnerMatcher(test_partners)
    linker = PartnerLinker(config=LinkConfig(dry_run=True))
    reporter = LinkReportGenerator()

    # テストケース
    test_cases = [
        ("セブンイレブン代々木", "株式会社セブン-イレブン・ジャパン", "8011101021428"),
        ("トイザラス熊本店", "日本トイザらス株式会社", None),
        ("山田商店", None, None),
    ]

    print("=== 紐付けテスト ===\n")

    for tx_name, parent, corp_num in test_cases:
        print(f"明細: {tx_name}")

        candidates = matcher.match_by_name(parent, corp_num) if parent else []
        proposal = linker.create_proposal(tx_name, parent, corp_num, candidates)
        reporter.add_proposal(proposal)

        print(f"  → アクション: {proposal['action']}")
        print(f"     確信度: {proposal['confidence']}")
        print(f"     理由: {proposal['reason']}")
        print()

    reporter.print_summary()
