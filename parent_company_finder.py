"""
親会社特定モジュール

銀行/カード明細の取引先名から、正式な法人名を特定する。
例: "トイザラス熊本店" → "日本トイザらス株式会社"
例: "セブンイレブン代々木" → "株式会社セブン-イレブン・ジャパン"
"""

import json
import os
import hashlib
from pathlib import Path
from typing import TypedDict
from anthropic import Anthropic


class ParentCompanyResult(TypedDict):
    """親会社特定の結果"""
    original_name: str          # 元の名前（明細に記載された名前）
    parent_company: str | None  # 特定された親会社名
    confidence: str             # 確信度: high, medium, low, unknown
    reasoning: str              # 判断理由
    is_individual: bool         # 個人事業主の可能性
    notes: str                  # 補足情報


class ParentCompanyFinder:
    """
    店舗名・支店名から親会社（法人）を特定するクラス。
    Claude APIを使用して企業情報を解析する。
    """

    SYSTEM_PROMPT = """あなたは日本の企業情報に詳しいアシスタントです。
銀行やクレジットカードの明細に記載される取引先名から、正式な法人名を特定してください。

## タスク
与えられた取引先名から、その店舗・サービスを運営している法人の正式名称を特定してください。

## ルール
1. 店舗名やサービス名ではなく、**登記されている法人名**を回答してください
2. フランチャイズの場合は、本部の法人名を回答してください
3. 個人事業主の可能性がある場合は、その旨を明記してください
4. 確信が持てない場合は、confidence を "low" または "unknown" としてください
5. グループ会社の場合、直接の運営会社を回答してください（持株会社ではなく）

## 例
- "トイザラス熊本店" → "日本トイザらス株式会社"
- "セブンイレブン代々木" → "株式会社セブン-イレブン・ジャパン"
- "ファミリーマート渋谷店" → "株式会社ファミリーマート"
- "スターバックス新宿" → "スターバックス コーヒー ジャパン株式会社"
- "山田電機商店" → 個人事業主の可能性あり

## 回答形式
必ず以下のJSON形式で回答してください:
{
  "parent_company": "法人名（特定できない場合はnull）",
  "confidence": "high | medium | low | unknown",
  "reasoning": "判断理由",
  "is_individual": false,
  "notes": "補足情報（任意）"
}"""

    def __init__(
        self,
        anthropic_api_key: str | None = None,
        cache_dir: str | None = None,
        model: str = "claude-sonnet-4-20250514"
    ) -> None:
        """
        初期化

        Args:
            anthropic_api_key: Anthropic APIキー（省略時は環境変数から取得）
            cache_dir: キャッシュディレクトリ（省略時はデフォルト）
            model: 使用するClaudeモデル
        """
        api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY が設定されていません")

        self.client = Anthropic(api_key=api_key)
        self.model = model

        # キャッシュディレクトリの設定
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(__file__).parent / ".cache" / "parent_company"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, name: str) -> str:
        """キャッシュキーを生成"""
        return hashlib.md5(name.encode()).hexdigest()

    def _get_cached_result(self, name: str) -> ParentCompanyResult | None:
        """キャッシュから結果を取得"""
        cache_file = self.cache_dir / f"{self._get_cache_key(name)}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def _save_to_cache(self, name: str, result: ParentCompanyResult) -> None:
        """結果をキャッシュに保存"""
        cache_file = self.cache_dir / f"{self._get_cache_key(name)}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Warning: キャッシュ保存に失敗: {e}")

    def find_parent_company(
        self,
        transaction_name: str,
        use_cache: bool = True
    ) -> ParentCompanyResult:
        """
        取引先名から親会社を特定する

        Args:
            transaction_name: 明細に記載された取引先名
            use_cache: キャッシュを使用するかどうか

        Returns:
            ParentCompanyResult: 親会社特定の結果
        """
        # キャッシュチェック
        if use_cache:
            cached = self._get_cached_result(transaction_name)
            if cached:
                return cached

        # Claude APIで親会社を特定
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"取引先名: {transaction_name}"
                    }
                ]
            )

            # レスポンスをパース
            response_text = message.content[0].text
            # JSON部分を抽出（マークダウンコードブロックに囲まれている場合も対応）
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()

            parsed = json.loads(json_str)

            result: ParentCompanyResult = {
                "original_name": transaction_name,
                "parent_company": parsed.get("parent_company"),
                "confidence": parsed.get("confidence", "unknown"),
                "reasoning": parsed.get("reasoning", ""),
                "is_individual": parsed.get("is_individual", False),
                "notes": parsed.get("notes", "")
            }

            # キャッシュに保存
            if use_cache:
                self._save_to_cache(transaction_name, result)

            return result

        except json.JSONDecodeError as e:
            return {
                "original_name": transaction_name,
                "parent_company": None,
                "confidence": "unknown",
                "reasoning": f"JSON解析エラー: {e}",
                "is_individual": False,
                "notes": f"Raw response: {response_text[:200] if 'response_text' in locals() else 'N/A'}"
            }
        except Exception as e:
            return {
                "original_name": transaction_name,
                "parent_company": None,
                "confidence": "unknown",
                "reasoning": f"API エラー: {e}",
                "is_individual": False,
                "notes": ""
            }

    def find_parent_companies_batch(
        self,
        transaction_names: list[str],
        use_cache: bool = True
    ) -> list[ParentCompanyResult]:
        """
        複数の取引先名から親会社を一括特定する

        Args:
            transaction_names: 明細に記載された取引先名のリスト
            use_cache: キャッシュを使用するかどうか

        Returns:
            list[ParentCompanyResult]: 親会社特定の結果リスト
        """
        results: list[ParentCompanyResult] = []
        for name in transaction_names:
            result = self.find_parent_company(name, use_cache)
            results.append(result)
        return results

    def clear_cache(self) -> int:
        """
        キャッシュをクリアする

        Returns:
            int: 削除されたキャッシュファイル数
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        return count


# テスト用
if __name__ == "__main__":
    # 環境変数 ANTHROPIC_API_KEY が設定されている前提
    try:
        finder = ParentCompanyFinder()

        test_names = [
            "トイザラス熊本店",
            "セブンイレブン代々木",
            "ファミリーマート渋谷店",
            "スターバックス新宿",
            "山田電機商店",  # 個人事業主の可能性
        ]

        print("=== 親会社特定テスト ===\n")
        for name in test_names:
            print(f"入力: {name}")
            result = finder.find_parent_company(name)
            print(f"  → 親会社: {result['parent_company']}")
            print(f"     確信度: {result['confidence']}")
            print(f"     理由: {result['reasoning']}")
            if result['is_individual']:
                print(f"     ⚠️ 個人事業主の可能性あり")
            print()

    except ValueError as e:
        print(f"エラー: {e}")
        print("ANTHROPIC_API_KEY を設定してください")
