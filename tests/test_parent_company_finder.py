"""
parent_company_finder.py のユニットテスト（モック使用）
"""

import json
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# anthropic モジュールをモックしてからインポート
sys.modules['anthropic'] = MagicMock()

from parent_company_finder import ParentCompanyFinder, ParentCompanyResult


class TestParentCompanyFinder(unittest.TestCase):
    """ParentCompanyFinderのテスト（APIモック使用）"""

    def setUp(self) -> None:
        """テスト準備"""
        self.mock_response = {
            "parent_company": "株式会社セブン-イレブン・ジャパン",
            "confidence": "high",
            "reasoning": "コンビニエンスストアチェーン",
            "is_individual": False,
            "notes": ""
        }

    @patch('parent_company_finder.Anthropic')
    def test_find_parent_company_success(self, mock_anthropic: Mock) -> None:
        """正常系: 親会社を正しく特定"""
        # モックのセットアップ
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(self.mock_response))]
        mock_client.messages.create.return_value = mock_message

        # テスト実行
        finder = ParentCompanyFinder(anthropic_api_key="test_key")
        result = finder.find_parent_company("セブンイレブン代々木", use_cache=False)

        # 検証
        self.assertEqual(result["parent_company"], "株式会社セブン-イレブン・ジャパン")
        self.assertEqual(result["confidence"], "high")
        self.assertFalse(result["is_individual"])

    @patch('parent_company_finder.Anthropic')
    def test_find_parent_company_with_markdown(self, mock_anthropic: Mock) -> None:
        """マークダウンコードブロック付きレスポンスの処理"""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # マークダウンで囲まれたJSON
        markdown_response = f"```json\n{json.dumps(self.mock_response)}\n```"
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=markdown_response)]
        mock_client.messages.create.return_value = mock_message

        finder = ParentCompanyFinder(anthropic_api_key="test_key")
        result = finder.find_parent_company("セブンイレブン", use_cache=False)

        self.assertEqual(result["parent_company"], "株式会社セブン-イレブン・ジャパン")

    @patch('parent_company_finder.Anthropic')
    def test_find_parent_company_individual(self, mock_anthropic: Mock) -> None:
        """個人事業主の可能性がある場合"""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        individual_response = {
            "parent_company": None,
            "confidence": "low",
            "reasoning": "個人事業主と思われる",
            "is_individual": True,
            "notes": "屋号のみで法人情報なし"
        }
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(individual_response))]
        mock_client.messages.create.return_value = mock_message

        finder = ParentCompanyFinder(anthropic_api_key="test_key")
        result = finder.find_parent_company("山田電機商店", use_cache=False)

        self.assertIsNone(result["parent_company"])
        self.assertTrue(result["is_individual"])
        self.assertEqual(result["confidence"], "low")

    @patch('parent_company_finder.Anthropic')
    def test_find_parent_company_api_error(self, mock_anthropic: Mock) -> None:
        """API エラー時の処理"""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API Error")

        finder = ParentCompanyFinder(anthropic_api_key="test_key")
        result = finder.find_parent_company("テスト", use_cache=False)

        self.assertIsNone(result["parent_company"])
        self.assertEqual(result["confidence"], "unknown")
        self.assertIn("API エラー", result["reasoning"])

    @patch('parent_company_finder.Anthropic')
    def test_find_parent_company_invalid_json(self, mock_anthropic: Mock) -> None:
        """不正なJSON レスポンス"""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="これはJSONではありません")]
        mock_client.messages.create.return_value = mock_message

        finder = ParentCompanyFinder(anthropic_api_key="test_key")
        result = finder.find_parent_company("テスト", use_cache=False)

        self.assertIsNone(result["parent_company"])
        self.assertEqual(result["confidence"], "unknown")
        self.assertIn("JSON解析エラー", result["reasoning"])

    def test_init_without_api_key(self) -> None:
        """APIキーなしでの初期化はエラー"""
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(ValueError) as context:
                ParentCompanyFinder(anthropic_api_key=None)
            self.assertIn("ANTHROPIC_API_KEY", str(context.exception))

    @patch('parent_company_finder.Anthropic')
    def test_batch_processing(self, mock_anthropic: Mock) -> None:
        """バッチ処理のテスト"""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(self.mock_response))]
        mock_client.messages.create.return_value = mock_message

        finder = ParentCompanyFinder(anthropic_api_key="test_key")
        names = ["セブンイレブン", "ファミマ", "ローソン"]
        results = finder.find_parent_companies_batch(names, use_cache=False)

        self.assertEqual(len(results), 3)
        self.assertEqual(mock_client.messages.create.call_count, 3)


class TestCacheKey(unittest.TestCase):
    """キャッシュキー生成のテスト"""

    @patch('parent_company_finder.Anthropic')
    def test_cache_key_consistency(self, mock_anthropic: Mock) -> None:
        """同じ入力に対して同じキャッシュキーを生成"""
        mock_anthropic.return_value = MagicMock()

        finder = ParentCompanyFinder(anthropic_api_key="test_key")

        key1 = finder._get_cache_key("テスト会社")
        key2 = finder._get_cache_key("テスト会社")
        key3 = finder._get_cache_key("別の会社")

        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3)

    @patch('parent_company_finder.Anthropic')
    def test_cache_key_length(self, mock_anthropic: Mock) -> None:
        """キャッシュキーは32文字（MD5ハッシュ）"""
        mock_anthropic.return_value = MagicMock()

        finder = ParentCompanyFinder(anthropic_api_key="test_key")
        key = finder._get_cache_key("テスト")

        self.assertEqual(len(key), 32)


if __name__ == "__main__":
    unittest.main()
