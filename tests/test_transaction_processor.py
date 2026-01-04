"""
transaction_processor.py の統合テスト
"""

import csv
import os
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# anthropic モジュールをモックしてからインポート
sys.modules['anthropic'] = MagicMock()

from transaction_processor import (
    TransactionProcessor,
    ProcessorConfig,
    TransactionInput,
    load_transactions_from_csv
)
from partner_matcher import PartnerData


class TestTransactionProcessor(unittest.TestCase):
    """TransactionProcessorの統合テスト"""

    def setUp(self) -> None:
        """テスト準備"""
        self.test_partners: list[PartnerData] = [
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

        self.config = ProcessorConfig(
            use_cache=False,
            dry_run=True,
            max_transactions=10
        )

    @patch('transaction_processor.FreeePartnerExporter')
    @patch('transaction_processor.ParentCompanyFinder')
    def test_process_transaction_with_match(
        self,
        mock_finder_class: Mock,
        mock_exporter_class: Mock
    ) -> None:
        """マッチする取引先がある場合"""
        # モックセットアップ
        mock_exporter = MagicMock()
        mock_exporter.get_partners.return_value = self.test_partners
        mock_exporter_class.return_value = mock_exporter

        mock_finder = MagicMock()
        mock_finder.find_parent_company.return_value = {
            "original_name": "セブンイレブン代々木",
            "parent_company": "株式会社セブン-イレブン・ジャパン",
            "confidence": "high",
            "reasoning": "コンビニチェーン",
            "is_individual": False,
            "notes": ""
        }
        mock_finder_class.return_value = mock_finder

        # テスト実行
        processor = TransactionProcessor(
            freee_access_token="test_token",
            anthropic_api_key="test_key",
            config=self.config
        )
        processor.load_partners(company_id=12345)

        transaction: TransactionInput = {
            "id": "1",
            "name": "セブンイレブン代々木",
            "amount": 1000,
            "date": "2026-01-04"
        }

        result = processor.process_transaction(transaction)

        # 検証
        self.assertEqual(result["action"], "link")
        self.assertEqual(result["target_partner_id"], 1)
        self.assertGreater(result["match_score"], 0.5)

    @patch('transaction_processor.FreeePartnerExporter')
    @patch('transaction_processor.ParentCompanyFinder')
    def test_process_transaction_no_match(
        self,
        mock_finder_class: Mock,
        mock_exporter_class: Mock
    ) -> None:
        """マッチする取引先がない場合は新規作成提案"""
        mock_exporter = MagicMock()
        mock_exporter.get_partners.return_value = self.test_partners
        mock_exporter_class.return_value = mock_exporter

        mock_finder = MagicMock()
        mock_finder.find_parent_company.return_value = {
            "original_name": "山田電機商店",
            "parent_company": "山田電機株式会社",
            "confidence": "medium",
            "reasoning": "推定",
            "is_individual": False,
            "notes": ""
        }
        mock_finder_class.return_value = mock_finder

        processor = TransactionProcessor(
            freee_access_token="test_token",
            anthropic_api_key="test_key",
            config=self.config
        )
        processor.load_partners(company_id=12345)

        transaction: TransactionInput = {
            "id": "2",
            "name": "山田電機商店",
            "amount": 5000,
            "date": "2026-01-04"
        }

        result = processor.process_transaction(transaction)

        # マッチなしなので create
        self.assertEqual(result["action"], "create")
        self.assertIsNone(result["target_partner_id"])

    @patch('transaction_processor.FreeePartnerExporter')
    @patch('transaction_processor.ParentCompanyFinder')
    def test_process_transaction_unknown_company(
        self,
        mock_finder_class: Mock,
        mock_exporter_class: Mock
    ) -> None:
        """親会社を特定できない場合はスキップ"""
        mock_exporter = MagicMock()
        mock_exporter.get_partners.return_value = self.test_partners
        mock_exporter_class.return_value = mock_exporter

        mock_finder = MagicMock()
        mock_finder.find_parent_company.return_value = {
            "original_name": "不明な取引先",
            "parent_company": None,
            "confidence": "unknown",
            "reasoning": "特定できず",
            "is_individual": False,
            "notes": ""
        }
        mock_finder_class.return_value = mock_finder

        processor = TransactionProcessor(
            freee_access_token="test_token",
            anthropic_api_key="test_key",
            config=self.config
        )
        processor.load_partners(company_id=12345)

        transaction: TransactionInput = {
            "id": "3",
            "name": "不明な取引先",
            "amount": 100,
            "date": "2026-01-04"
        }

        result = processor.process_transaction(transaction)

        self.assertEqual(result["action"], "skip")
        self.assertEqual(result["status"], "skipped")


class TestLoadTransactionsFromCSV(unittest.TestCase):
    """CSVロード機能のテスト"""

    def test_load_standard_csv(self) -> None:
        """標準フォーマットのCSV読み込み"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "amount", "date"])
            writer.writerow(["1", "セブンイレブン", "1000", "2026-01-04"])
            writer.writerow(["2", "ファミマ", "500", "2026-01-04"])
            temp_path = f.name

        try:
            transactions = load_transactions_from_csv(temp_path)
            self.assertEqual(len(transactions), 2)
            self.assertEqual(transactions[0]["name"], "セブンイレブン")
            self.assertEqual(transactions[0]["amount"], 1000)
        finally:
            os.unlink(temp_path)

    def test_load_japanese_header_csv(self) -> None:
        """日本語ヘッダーのCSV読み込み"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "取引先名", "金額", "日付"])
            writer.writerow(["1", "トイザらス", "", "2026-01-04"])
            temp_path = f.name

        try:
            transactions = load_transactions_from_csv(temp_path)
            self.assertEqual(len(transactions), 1)
            # 取引先名 が name にマッピングされる
            self.assertEqual(transactions[0]["name"], "トイザらス")
        finally:
            os.unlink(temp_path)


class TestProcessorConfig(unittest.TestCase):
    """ProcessorConfigのテスト"""

    def test_default_values(self) -> None:
        """デフォルト値の確認"""
        config = ProcessorConfig()
        self.assertTrue(config.use_cache)
        self.assertTrue(config.dry_run)
        self.assertEqual(config.max_transactions, 0)
        self.assertEqual(config.auto_link_threshold, 0.9)
        self.assertEqual(config.suggest_threshold, 0.6)

    def test_custom_values(self) -> None:
        """カスタム値の確認"""
        config = ProcessorConfig(
            use_cache=False,
            dry_run=False,
            max_transactions=100,
            auto_link_threshold=0.8
        )
        self.assertFalse(config.use_cache)
        self.assertFalse(config.dry_run)
        self.assertEqual(config.max_transactions, 100)
        self.assertEqual(config.auto_link_threshold, 0.8)


if __name__ == "__main__":
    unittest.main()
