"""
partner_linker.py のユニットテスト
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from partner_matcher import MatchCandidate, PartnerData
from partner_linker import PartnerLinker, LinkConfig, LinkReportGenerator


class TestPartnerLinker(unittest.TestCase):
    """PartnerLinkerのテスト"""

    def setUp(self) -> None:
        """テスト用データを準備"""
        self.config = LinkConfig(
            auto_link_threshold=0.9,
            suggest_threshold=0.6,
            dry_run=True
        )
        self.linker = PartnerLinker(config=self.config)

        self.test_partner: PartnerData = {
            "id": 1,
            "name": "株式会社セブン-イレブン・ジャパン",
            "shortcut1": "セブンイレブン",
            "shortcut2": None,
            "long_name": None,
            "corporate_number": "8011101021428"
        }

    def test_create_proposal_no_parent(self) -> None:
        """親会社特定できない場合はスキップ"""
        proposal = self.linker.create_proposal(
            transaction_name="不明な取引先",
            parent_company=None,
            corporate_number=None,
            candidates=[]
        )
        self.assertEqual(proposal["action"], "skip")
        self.assertEqual(proposal["confidence"], "unknown")

    def test_create_proposal_no_candidates(self) -> None:
        """候補なしの場合は新規作成を提案"""
        proposal = self.linker.create_proposal(
            transaction_name="トイザラス熊本店",
            parent_company="日本トイザらス株式会社",
            corporate_number="4010401089234",
            candidates=[]
        )
        self.assertEqual(proposal["action"], "create")
        self.assertEqual(proposal["confidence"], "medium")  # 法人番号あり

    def test_create_proposal_high_score(self) -> None:
        """高スコアの場合は自動紐付け"""
        candidate: MatchCandidate = {
            "partner": self.test_partner,
            "score": 0.95,
            "match_type": "exact_name",
            "matched_field": "name"
        }
        proposal = self.linker.create_proposal(
            transaction_name="セブンイレブン代々木",
            parent_company="株式会社セブン-イレブン・ジャパン",
            corporate_number=None,
            candidates=[candidate]
        )
        self.assertEqual(proposal["action"], "link")
        self.assertEqual(proposal["confidence"], "high")
        self.assertEqual(proposal["target_partner"]["id"], 1)

    def test_create_proposal_medium_score(self) -> None:
        """中スコアの場合は確認が必要"""
        candidate: MatchCandidate = {
            "partner": self.test_partner,
            "score": 0.75,
            "match_type": "partial_match",
            "matched_field": "shortcut1"
        }
        proposal = self.linker.create_proposal(
            transaction_name="セブン",
            parent_company="セブン-イレブン",
            corporate_number=None,
            candidates=[candidate]
        )
        self.assertEqual(proposal["action"], "link")
        self.assertEqual(proposal["confidence"], "medium")

    def test_create_proposal_low_score(self) -> None:
        """低スコアの場合は新規作成を提案"""
        candidate: MatchCandidate = {
            "partner": self.test_partner,
            "score": 0.4,
            "match_type": "name_similarity",
            "matched_field": "name"
        }
        proposal = self.linker.create_proposal(
            transaction_name="全く別の会社",
            parent_company="別の会社株式会社",
            corporate_number=None,
            candidates=[candidate]
        )
        self.assertEqual(proposal["action"], "create")
        self.assertEqual(proposal["confidence"], "low")

    def test_execute_link_dry_run(self) -> None:
        """ドライランでは実際に更新しない"""
        candidate: MatchCandidate = {
            "partner": self.test_partner,
            "score": 0.95,
            "match_type": "exact_name",
            "matched_field": "name"
        }
        proposal = self.linker.create_proposal(
            transaction_name="セブンイレブン",
            parent_company="株式会社セブン-イレブン・ジャパン",
            corporate_number=None,
            candidates=[candidate]
        )
        result = self.linker.execute_link(company_id=12345, proposal=proposal)
        self.assertEqual(result["status"], "skipped")
        self.assertIn("DRY RUN", result["message"])


class TestLinkReportGenerator(unittest.TestCase):
    """LinkReportGeneratorのテスト"""

    def setUp(self) -> None:
        self.reporter = LinkReportGenerator()

    def test_add_proposal(self) -> None:
        """提案の追加"""
        proposal = {
            "transaction_name": "テスト取引",
            "parent_company": "テスト株式会社",
            "corporate_number": "1234567890123",
            "action": "link",
            "target_partner": None,
            "match_score": 0.9,
            "confidence": "high",
            "reason": "テスト理由"
        }
        self.reporter.add_proposal(proposal)
        self.assertEqual(len(self.reporter.proposals), 1)

    def test_add_result(self) -> None:
        """結果の追加"""
        result = {
            "transaction_name": "テスト取引",
            "action": "link",
            "status": "success",
            "message": "成功",
            "partner_id": 1
        }
        self.reporter.add_result(result)
        self.assertEqual(len(self.reporter.results), 1)


class TestLinkConfig(unittest.TestCase):
    """LinkConfigのテスト"""

    def test_default_values(self) -> None:
        """デフォルト値のテスト"""
        config = LinkConfig()
        self.assertEqual(config.auto_link_threshold, 0.9)
        self.assertEqual(config.suggest_threshold, 0.6)
        self.assertTrue(config.create_new_if_no_match)
        self.assertTrue(config.dry_run)

    def test_custom_values(self) -> None:
        """カスタム値のテスト"""
        config = LinkConfig(
            auto_link_threshold=0.8,
            suggest_threshold=0.5,
            dry_run=False
        )
        self.assertEqual(config.auto_link_threshold, 0.8)
        self.assertEqual(config.suggest_threshold, 0.5)
        self.assertFalse(config.dry_run)


if __name__ == "__main__":
    unittest.main()
