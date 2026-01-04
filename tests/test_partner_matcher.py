"""
partner_matcher.py のユニットテスト
"""

import unittest
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from partner_matcher import PartnerMatcher, MatchConfig, PartnerData


class TestPartnerMatcher(unittest.TestCase):
    """PartnerMatcherのテスト"""

    def setUp(self) -> None:
        """テスト用データを準備"""
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
            },
            {
                "id": 3,
                "name": "株式会社ファミリーマート",
                "shortcut1": "ファミマ",
                "shortcut2": "ファミリーマート",
                "long_name": None,
                "corporate_number": "7010001098262"
            },
            {
                "id": 4,
                "name": "スターバックス コーヒー ジャパン株式会社",
                "shortcut1": "スタバ",
                "shortcut2": None,
                "long_name": "スターバックスコーヒージャパン",
                "corporate_number": "9010401039817"
            }
        ]
        self.matcher = PartnerMatcher(self.test_partners)

    def test_exact_corporate_number_match(self) -> None:
        """法人番号での完全一致テスト"""
        result = self.matcher.match_by_corporate_number("8011101021428")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 1)
        self.assertEqual(result["name"], "株式会社セブン-イレブン・ジャパン")

    def test_corporate_number_not_found(self) -> None:
        """存在しない法人番号のテスト"""
        result = self.matcher.match_by_corporate_number("0000000000000")
        self.assertIsNone(result)

    def test_exact_name_match(self) -> None:
        """名前の完全一致テスト"""
        candidates = self.matcher.match_by_name("株式会社セブン-イレブン・ジャパン")
        self.assertTrue(len(candidates) > 0)
        self.assertEqual(candidates[0]["partner"]["id"], 1)
        self.assertGreaterEqual(candidates[0]["score"], 0.95)

    def test_partial_name_match(self) -> None:
        """名前の部分一致テスト"""
        candidates = self.matcher.match_by_name("セブンイレブン代々木")
        self.assertTrue(len(candidates) > 0)
        # セブン-イレブン・ジャパンがマッチするはず
        self.assertEqual(candidates[0]["partner"]["id"], 1)

    def test_shortcut_match(self) -> None:
        """ショートカット名でのマッチテスト"""
        candidates = self.matcher.match_by_name("ファミマ")
        self.assertTrue(len(candidates) > 0)
        self.assertEqual(candidates[0]["partner"]["id"], 3)

    def test_no_match(self) -> None:
        """マッチなしのテスト"""
        candidates = self.matcher.match_by_name("存在しない会社名")
        # 閾値以下なのでマッチなし
        self.assertEqual(len(candidates), 0)

    def test_match_with_corporate_number_priority(self) -> None:
        """法人番号がある場合は最優先でマッチ"""
        candidates = self.matcher.match_by_name(
            "全く違う名前",
            corporate_number="4010401089234"
        )
        self.assertTrue(len(candidates) > 0)
        self.assertEqual(candidates[0]["partner"]["id"], 2)
        self.assertEqual(candidates[0]["match_type"], "exact_corp_num")

    def test_similarity_score_range(self) -> None:
        """類似度スコアが0-1の範囲であること"""
        candidates = self.matcher.match_by_name("スターバックス")
        for c in candidates:
            self.assertGreaterEqual(c["score"], 0.0)
            self.assertLessEqual(c["score"], 1.0)

    def test_max_candidates_limit(self) -> None:
        """最大候補数の制限テスト"""
        config = MatchConfig(max_candidates=2, min_score=0.1)
        matcher = PartnerMatcher(self.test_partners, config)
        candidates = matcher.match_by_name("株式会社")
        self.assertLessEqual(len(candidates), 2)

    def test_normalize_fullwidth(self) -> None:
        """全角→半角変換のテスト"""
        # 全角で検索しても半角と同様にマッチ
        candidates = self.matcher.match_by_name("ファミリーマート")
        self.assertTrue(len(candidates) > 0)


class TestSimilarityCalculation(unittest.TestCase):
    """類似度計算のテスト"""

    def setUp(self) -> None:
        self.matcher = PartnerMatcher([])

    def test_identical_strings(self) -> None:
        """同一文字列の類似度は1.0"""
        score = self.matcher._similarity_score("テスト", "テスト")
        self.assertEqual(score, 1.0)

    def test_completely_different(self) -> None:
        """全く異なる文字列の類似度は低い"""
        score = self.matcher._similarity_score("あいうえお", "かきくけこ")
        self.assertLess(score, 0.5)

    def test_substring_match(self) -> None:
        """部分文字列は高い類似度"""
        score = self.matcher._similarity_score("セブンイレブン", "セブンイレブン代々木")
        self.assertGreater(score, 0.7)

    def test_jaro_winkler_identical(self) -> None:
        """Jaro-Winkler: 同一文字列は1.0"""
        score = self.matcher._jaro_winkler("テスト", "テスト")
        self.assertEqual(score, 1.0)

    def test_jaro_winkler_empty(self) -> None:
        """Jaro-Winkler: 空文字列は0.0"""
        score = self.matcher._jaro_winkler("", "テスト")
        self.assertEqual(score, 0.0)


if __name__ == "__main__":
    unittest.main()
