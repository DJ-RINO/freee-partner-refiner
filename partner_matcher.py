"""
取引先マッチングエンジン

freee既存取引先と親会社名をマッチングし、紐付け候補を提案する。
"""

import re
from dataclasses import dataclass
from typing import TypedDict


class PartnerData(TypedDict):
    """freee取引先データ"""
    id: int
    name: str
    shortcut1: str | None
    shortcut2: str | None
    long_name: str | None
    corporate_number: str | None


class MatchCandidate(TypedDict):
    """マッチング候補"""
    partner: PartnerData
    score: float           # 0.0 - 1.0
    match_type: str        # exact_corp_num, name_similarity, partial_match
    matched_field: str     # name, shortcut1, shortcut2, long_name, corporate_number


@dataclass
class MatchConfig:
    """マッチング設定"""
    min_score: float = 0.6           # 最低スコア閾値
    max_candidates: int = 5          # 最大候補数
    exact_match_boost: float = 0.3   # 完全一致ボーナス
    corp_num_weight: float = 1.0     # 法人番号一致の重み


class PartnerMatcher:
    """
    取引先マッチングエンジン

    親会社名とfreee既存取引先をマッチングし、
    最も適切な紐付け先を提案する。
    """

    def __init__(self, partners: list[PartnerData], config: MatchConfig | None = None) -> None:
        """
        初期化

        Args:
            partners: freee取引先リスト
            config: マッチング設定
        """
        self.partners = partners
        self.config = config or MatchConfig()

        # インデックス作成
        self._build_index()

    def _build_index(self) -> None:
        """検索用インデックスを構築"""
        # 正規化した名前 → パートナーリスト
        self.name_index: dict[str, list[PartnerData]] = {}
        # 法人番号 → パートナー
        self.corp_num_index: dict[str, PartnerData] = {}

        for partner in self.partners:
            # 名前のインデックス
            for field in ["name", "shortcut1", "shortcut2", "long_name"]:
                value = partner.get(field)
                if value:
                    normalized = self._normalize(value)
                    if normalized not in self.name_index:
                        self.name_index[normalized] = []
                    self.name_index[normalized].append(partner)

            # 法人番号のインデックス
            corp_num = partner.get("corporate_number")
            if corp_num:
                self.corp_num_index[corp_num] = partner

    def _normalize(self, text: str) -> str:
        """テキストを正規化"""
        # 全角→半角
        text = text.translate(str.maketrans(
            'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ０１２３４５６７８９',
            'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        ))
        # 小文字化
        text = text.lower()
        # 空白・記号除去
        text = re.sub(r'[\s\-・．.。、,（）()「」【】\[\]]+', '', text)
        # 法人格を除去
        text = re.sub(r'(株式会社|有限会社|合同会社|合資会社|株|有|㈱|㈲)', '', text)
        return text

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """レーベンシュタイン距離を計算"""
        if len(s1) < len(s2):
            s1, s2 = s2, s1

        if len(s2) == 0:
            return len(s1)

        prev_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row

        return prev_row[-1]

    def _similarity_score(self, s1: str, s2: str) -> float:
        """類似度スコアを計算 (0.0 - 1.0)"""
        s1_norm = self._normalize(s1)
        s2_norm = self._normalize(s2)

        if not s1_norm or not s2_norm:
            return 0.0

        # 完全一致
        if s1_norm == s2_norm:
            return 1.0

        # 部分一致（片方が片方を含む）
        if s1_norm in s2_norm or s2_norm in s1_norm:
            shorter = min(len(s1_norm), len(s2_norm))
            longer = max(len(s1_norm), len(s2_norm))
            return 0.7 + 0.3 * (shorter / longer)

        # レーベンシュタイン距離ベースの類似度
        distance = self._levenshtein_distance(s1_norm, s2_norm)
        max_len = max(len(s1_norm), len(s2_norm))
        return max(0.0, 1.0 - (distance / max_len))

    def _jaro_winkler(self, s1: str, s2: str) -> float:
        """Jaro-Winkler類似度を計算"""
        s1_norm = self._normalize(s1)
        s2_norm = self._normalize(s2)

        if not s1_norm or not s2_norm:
            return 0.0

        if s1_norm == s2_norm:
            return 1.0

        len1, len2 = len(s1_norm), len(s2_norm)
        match_distance = max(len1, len2) // 2 - 1
        if match_distance < 0:
            match_distance = 0

        s1_matches = [False] * len1
        s2_matches = [False] * len2

        matches = 0
        transpositions = 0

        for i in range(len1):
            start = max(0, i - match_distance)
            end = min(i + match_distance + 1, len2)

            for j in range(start, end):
                if s2_matches[j] or s1_norm[i] != s2_norm[j]:
                    continue
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

        if matches == 0:
            return 0.0

        k = 0
        for i in range(len1):
            if not s1_matches[i]:
                continue
            while not s2_matches[k]:
                k += 1
            if s1_norm[i] != s2_norm[k]:
                transpositions += 1
            k += 1

        jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3

        # Winklerの調整（共通接頭辞ボーナス）
        prefix = 0
        for i in range(min(len1, len2, 4)):
            if s1_norm[i] == s2_norm[i]:
                prefix += 1
            else:
                break

        return jaro + prefix * 0.1 * (1 - jaro)

    def match_by_corporate_number(self, corporate_number: str) -> PartnerData | None:
        """法人番号で完全一致検索"""
        return self.corp_num_index.get(corporate_number)

    def match_by_name(
        self,
        name: str,
        corporate_number: str | None = None
    ) -> list[MatchCandidate]:
        """
        名前で類似検索

        Args:
            name: 検索する名前（親会社名）
            corporate_number: 法人番号（あれば完全一致優先）

        Returns:
            マッチング候補リスト（スコア降順）
        """
        candidates: list[MatchCandidate] = []
        seen_ids: set[int] = set()

        # 1. 法人番号での完全一致（最優先）
        if corporate_number:
            exact_match = self.match_by_corporate_number(corporate_number)
            if exact_match:
                candidates.append({
                    "partner": exact_match,
                    "score": 1.0,
                    "match_type": "exact_corp_num",
                    "matched_field": "corporate_number"
                })
                seen_ids.add(exact_match["id"])

        # 2. 名前の類似度検索
        name_norm = self._normalize(name)

        for partner in self.partners:
            if partner["id"] in seen_ids:
                continue

            best_score = 0.0
            best_field = ""

            for field in ["name", "long_name", "shortcut1", "shortcut2"]:
                value = partner.get(field)
                if not value:
                    continue

                # レーベンシュタインとJaro-Winklerの平均
                lev_score = self._similarity_score(name, value)
                jw_score = self._jaro_winkler(name, value)
                score = (lev_score + jw_score) / 2

                # 完全一致ボーナス
                if self._normalize(value) == name_norm:
                    score = min(1.0, score + self.config.exact_match_boost)

                if score > best_score:
                    best_score = score
                    best_field = field

            if best_score >= self.config.min_score:
                match_type = "exact_name" if best_score >= 0.95 else "name_similarity"
                if best_score >= 0.7 and best_score < 0.95:
                    match_type = "partial_match"

                candidates.append({
                    "partner": partner,
                    "score": best_score,
                    "match_type": match_type,
                    "matched_field": best_field
                })
                seen_ids.add(partner["id"])

        # スコア降順でソート
        candidates.sort(key=lambda x: x["score"], reverse=True)

        # 最大候補数で制限
        return candidates[:self.config.max_candidates]

    def find_best_match(
        self,
        parent_company: str,
        corporate_number: str | None = None
    ) -> MatchCandidate | None:
        """
        最適なマッチを1件返す

        Args:
            parent_company: 親会社名
            corporate_number: 法人番号

        Returns:
            最適な候補、なければNone
        """
        candidates = self.match_by_name(parent_company, corporate_number)
        return candidates[0] if candidates else None


class PartnerIndex:
    """
    取引先インデックス

    freee取引先を効率的に検索するためのインデックス。
    """

    def __init__(self) -> None:
        self.partners: list[PartnerData] = []
        self.matcher: PartnerMatcher | None = None

    def load_from_freee(self, partners: list[PartnerData]) -> None:
        """freeeから取得した取引先をロード"""
        self.partners = partners
        self.matcher = PartnerMatcher(partners)

    def search(
        self,
        query: str,
        corporate_number: str | None = None,
        config: MatchConfig | None = None
    ) -> list[MatchCandidate]:
        """
        取引先を検索

        Args:
            query: 検索クエリ（親会社名）
            corporate_number: 法人番号
            config: マッチング設定

        Returns:
            マッチング候補リスト
        """
        if not self.matcher:
            return []

        if config:
            self.matcher.config = config

        return self.matcher.match_by_name(query, corporate_number)

    def get_stats(self) -> dict:
        """インデックスの統計情報"""
        total = len(self.partners)
        with_corp_num = sum(1 for p in self.partners if p.get("corporate_number"))
        return {
            "total_partners": total,
            "with_corporate_number": with_corp_num,
            "without_corporate_number": total - with_corp_num
        }


# テスト用
if __name__ == "__main__":
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

    # マッチャーを作成
    matcher = PartnerMatcher(test_partners)

    # テストケース
    test_queries = [
        ("株式会社セブン-イレブン・ジャパン", None),  # 完全一致
        ("セブンイレブン代々木", None),                # 部分一致
        ("トイザらス", "4010401089234"),              # 法人番号一致
        ("ファミリーマート渋谷店", None),              # 部分一致
        ("スターバックス新宿", None),                  # 部分一致
        ("山田商店", None),                           # マッチなし
    ]

    print("=== マッチングテスト ===\n")
    for query, corp_num in test_queries:
        print(f"検索: {query}")
        if corp_num:
            print(f"       法人番号: {corp_num}")

        candidates = matcher.match_by_name(query, corp_num)

        if candidates:
            for i, c in enumerate(candidates, 1):
                print(f"  [{i}] {c['partner']['name']}")
                print(f"      スコア: {c['score']:.2f}, タイプ: {c['match_type']}, フィールド: {c['matched_field']}")
        else:
            print("  → マッチなし")
        print()
