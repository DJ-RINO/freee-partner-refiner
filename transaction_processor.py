"""
取引処理統合スクリプト

銀行/カード明細から取引先を特定し、freee取引先に紐付けるメインスクリプト。

フロー:
1. 明細の取引先名を取得
2. 親会社を特定（Claude API）
3. freee既存取引先とマッチング
4. 紐付け提案を生成
5. 確認後、実行
"""

import csv
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict

from batch_export import FreeePartnerExporter
from parent_company_finder import ParentCompanyFinder, ParentCompanyResult
from partner_matcher import PartnerMatcher, MatchConfig, PartnerData
from partner_linker import PartnerLinker, LinkConfig, LinkReportGenerator


class TransactionInput(TypedDict):
    """処理対象の取引"""
    id: str | int
    name: str           # 明細に記載された取引先名
    amount: int | None  # 金額（任意）
    date: str | None    # 日付（任意）


class ProcessResult(TypedDict):
    """処理結果"""
    transaction: TransactionInput
    parent_company: ParentCompanyResult
    match_score: float
    action: str
    target_partner_id: int | None
    target_partner_name: str | None
    status: str
    message: str


@dataclass
class ProcessorConfig:
    """処理設定"""
    use_cache: bool = True              # 親会社特定のキャッシュを使用
    auto_link_threshold: float = 0.9    # 自動紐付け閾値
    suggest_threshold: float = 0.6      # 提案表示閾値
    dry_run: bool = True                # ドライラン
    max_transactions: int = 0           # 最大処理件数（0=無制限）


class TransactionProcessor:
    """
    取引処理統合クラス

    銀行/カード明細を処理し、freee取引先への紐付けを提案・実行する。
    """

    def __init__(
        self,
        freee_access_token: str | None = None,
        anthropic_api_key: str | None = None,
        config: ProcessorConfig | None = None
    ) -> None:
        """
        初期化

        Args:
            freee_access_token: freee APIトークン
            anthropic_api_key: Anthropic APIキー
            config: 処理設定
        """
        self.config = config or ProcessorConfig()

        # freeeエクスポーター
        self.exporter = FreeePartnerExporter(freee_access_token)

        # 親会社特定
        self.finder = ParentCompanyFinder(anthropic_api_key)

        # 紐付け
        link_config = LinkConfig(
            auto_link_threshold=self.config.auto_link_threshold,
            suggest_threshold=self.config.suggest_threshold,
            dry_run=self.config.dry_run
        )
        self.linker = PartnerLinker(freee_access_token, link_config)

        # レポート
        self.reporter = LinkReportGenerator()

        # マッチャー（後で初期化）
        self.matcher: PartnerMatcher | None = None

    def load_partners(self, company_id: int) -> None:
        """freee取引先をロードしてインデックス化"""
        print("📥 freee取引先を読み込み中...")
        partners_raw = self.exporter.get_partners(company_id)

        # PartnerData形式に変換
        partners: list[PartnerData] = []
        for p in partners_raw:
            partners.append({
                "id": p["id"],
                "name": p["name"],
                "shortcut1": p.get("shortcut1"),
                "shortcut2": p.get("shortcut2"),
                "long_name": p.get("long_name"),
                "corporate_number": p.get("corporate_number")
            })

        self.matcher = PartnerMatcher(partners, MatchConfig(
            min_score=self.config.suggest_threshold
        ))

        total = len(partners)
        with_corp = sum(1 for p in partners if p.get("corporate_number"))
        print(f"   ✅ {total}件の取引先をロード（法人番号あり: {with_corp}件）")

    def process_transaction(
        self,
        transaction: TransactionInput
    ) -> ProcessResult:
        """
        1件の取引を処理

        Args:
            transaction: 処理対象の取引

        Returns:
            処理結果
        """
        tx_name = transaction["name"]

        # Step 1: 親会社を特定
        parent_result = self.finder.find_parent_company(
            tx_name,
            use_cache=self.config.use_cache
        )

        parent_company = parent_result["parent_company"]
        confidence = parent_result["confidence"]

        if not parent_company:
            return {
                "transaction": transaction,
                "parent_company": parent_result,
                "match_score": 0.0,
                "action": "skip",
                "target_partner_id": None,
                "target_partner_name": None,
                "status": "skipped",
                "message": f"親会社を特定できませんでした（確信度: {confidence}）"
            }

        # Step 2: 既存取引先とマッチング
        if not self.matcher:
            return {
                "transaction": transaction,
                "parent_company": parent_result,
                "match_score": 0.0,
                "action": "skip",
                "target_partner_id": None,
                "target_partner_name": None,
                "status": "error",
                "message": "取引先インデックスが未初期化です"
            }

        candidates = self.matcher.match_by_name(parent_company)

        # Step 3: 紐付け提案を作成
        proposal = self.linker.create_proposal(
            transaction_name=tx_name,
            parent_company=parent_company,
            corporate_number=None,  # gBizINFOで後から取得可能
            candidates=candidates
        )

        self.reporter.add_proposal(proposal)

        target_partner = proposal["target_partner"]

        return {
            "transaction": transaction,
            "parent_company": parent_result,
            "match_score": proposal["match_score"],
            "action": proposal["action"],
            "target_partner_id": target_partner["id"] if target_partner else None,
            "target_partner_name": target_partner["name"] if target_partner else None,
            "status": "processed",
            "message": proposal["reason"]
        }

    def process_batch(
        self,
        transactions: list[TransactionInput],
        company_id: int
    ) -> list[ProcessResult]:
        """
        複数の取引を一括処理

        Args:
            transactions: 処理対象の取引リスト
            company_id: 事業所ID

        Returns:
            処理結果リスト
        """
        # 取引先をロード
        self.load_partners(company_id)

        results: list[ProcessResult] = []
        total = len(transactions)

        if self.config.max_transactions > 0:
            transactions = transactions[:self.config.max_transactions]
            print(f"\n⚠️  処理件数制限: {self.config.max_transactions}件")

        print(f"\n🔄 {len(transactions)}件の取引を処理中...\n")

        for i, tx in enumerate(transactions, 1):
            print(f"[{i}/{len(transactions)}] {tx['name'][:30]}...")

            result = self.process_transaction(tx)
            results.append(result)

            # 簡易進捗表示
            if result["action"] == "link":
                print(f"   → 🔗 {result['target_partner_name']} (スコア: {result['match_score']:.2f})")
            elif result["action"] == "create":
                print(f"   → ➕ 新規作成推奨: {result['parent_company']['parent_company']}")
            else:
                print(f"   → ⏭️ スキップ: {result['message'][:40]}")

        return results

    def export_results(
        self,
        results: list[ProcessResult],
        output_path: str | None = None
    ) -> str:
        """
        結果をCSVにエクスポート

        Args:
            results: 処理結果リスト
            output_path: 出力パス

        Returns:
            出力ファイルパス
        """
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"transaction_results_{timestamp}.csv"

        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "取引ID",
                "明細取引先名",
                "特定された親会社",
                "確信度",
                "アクション",
                "紐付け先ID",
                "紐付け先名",
                "スコア",
                "ステータス",
                "メッセージ"
            ])

            for r in results:
                writer.writerow([
                    r["transaction"]["id"],
                    r["transaction"]["name"],
                    r["parent_company"]["parent_company"] or "",
                    r["parent_company"]["confidence"],
                    r["action"],
                    r["target_partner_id"] or "",
                    r["target_partner_name"] or "",
                    f"{r['match_score']:.2f}",
                    r["status"],
                    r["message"]
                ])

        print(f"\n📄 結果をエクスポート: {output_path}")
        return output_path

    def print_summary(self, results: list[ProcessResult]) -> None:
        """サマリーを表示"""
        total = len(results)
        actions = {}
        for r in results:
            actions[r["action"]] = actions.get(r["action"], 0) + 1

        print("\n" + "=" * 50)
        print("📊 処理結果サマリー")
        print("=" * 50)
        print(f"\n合計: {total}件")
        print("\nアクション別:")
        for action, count in actions.items():
            icon = {"link": "🔗 紐付け", "create": "➕ 新規作成", "skip": "⏭️ スキップ"}.get(action, action)
            pct = count / total * 100 if total > 0 else 0
            print(f"   {icon}: {count}件 ({pct:.1f}%)")

        # 紐付け候補のレポートも出力
        self.reporter.print_summary()


def load_transactions_from_csv(csv_path: str) -> list[TransactionInput]:
    """CSVから取引を読み込み"""
    transactions: list[TransactionInput] = []

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append({
                "id": row.get("id", row.get("ID", "")),
                "name": row.get("name", row.get("取引先名", row.get("取引先", ""))),
                "amount": int(row["amount"]) if row.get("amount") else None,
                "date": row.get("date", row.get("日付"))
            })

    return transactions


def show_usage() -> None:
    """使用方法を表示"""
    print("""
取引処理統合スクリプト

使用方法:
  python transaction_processor.py <transactions.csv> [options]

オプション:
  --limit N       最大処理件数（デフォルト: 10）
  --threshold N   紐付け閾値（デフォルト: 0.6）
  --no-cache      キャッシュを使用しない
  --execute       実際に更新を実行（デフォルトはドライラン）

環境変数:
  FREEE_ACCESS_TOKEN   freee APIアクセストークン（必須）
  FREEE_COMPANY_ID     freee事業所ID（必須）
  ANTHROPIC_API_KEY    Claude APIキー（必須）

入力CSVフォーマット:
  id,name,amount,date
  1,トイザラス熊本店,5000,2026-01-01
  2,セブンイレブン代々木,1200,2026-01-02

例:
  # ドライラン（最初の10件）
  python transaction_processor.py transactions.csv --limit 10

  # 全件処理（実行）
  python transaction_processor.py transactions.csv --limit 0 --execute
""")


def main() -> None:
    """メイン処理"""
    if len(sys.argv) < 2:
        show_usage()
        sys.exit(1)

    csv_path = sys.argv[1]

    # オプション解析
    limit = 10
    threshold = 0.6
    use_cache = True
    dry_run = True

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        elif args[i] == "--threshold" and i + 1 < len(args):
            threshold = float(args[i + 1])
            i += 2
        elif args[i] == "--no-cache":
            use_cache = False
            i += 1
        elif args[i] == "--execute":
            dry_run = False
            i += 1
        else:
            i += 1

    # 環境変数チェック
    required_vars = ["FREEE_ACCESS_TOKEN", "FREEE_COMPANY_ID", "ANTHROPIC_API_KEY"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(f"❌ 必要な環境変数が設定されていません: {', '.join(missing)}")
        sys.exit(1)

    company_id = int(os.environ["FREEE_COMPANY_ID"])

    # 設定
    config = ProcessorConfig(
        use_cache=use_cache,
        suggest_threshold=threshold,
        auto_link_threshold=threshold + 0.2,
        dry_run=dry_run,
        max_transactions=limit
    )

    print("=" * 50)
    print("🚀 取引処理統合スクリプト")
    print("=" * 50)
    print(f"\n入力: {csv_path}")
    print(f"モード: {'ドライラン' if dry_run else '⚠️ 実行モード'}")
    print(f"処理上限: {limit if limit > 0 else '無制限'}")
    print(f"閾値: {threshold}")

    # 取引を読み込み
    try:
        transactions = load_transactions_from_csv(csv_path)
        print(f"\n📄 {len(transactions)}件の取引を読み込みました")
    except FileNotFoundError:
        print(f"❌ ファイルが見つかりません: {csv_path}")
        sys.exit(1)

    # 処理実行
    processor = TransactionProcessor(config=config)
    results = processor.process_batch(transactions, company_id)

    # サマリー表示
    processor.print_summary(results)

    # 結果エクスポート
    processor.export_results(results)

    # 提案レポートも出力
    proposal_path = processor.reporter.generate_proposal_report()
    print(f"📄 提案レポート: {proposal_path}")


if __name__ == "__main__":
    main()
