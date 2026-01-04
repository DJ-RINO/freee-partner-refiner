"""
カスタム例外クラス

プロジェクト固有のエラーを定義する。
"""


class PartnerRefinerError(Exception):
    """プロジェクト基底例外クラス"""

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class ConfigurationError(PartnerRefinerError):
    """設定エラー（環境変数未設定など）"""
    pass


class APIError(PartnerRefinerError):
    """外部API関連のエラー"""

    def __init__(
        self,
        message: str,
        api_name: str,
        status_code: int | None = None,
        response_body: str | None = None
    ) -> None:
        super().__init__(message, response_body)
        self.api_name = api_name
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        base = f"[{self.api_name}] {self.message}"
        if self.status_code:
            base += f" (HTTP {self.status_code})"
        return base


class FreeeAPIError(APIError):
    """freee API固有のエラー"""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None
    ) -> None:
        super().__init__(message, "freee API", status_code, response_body)


class AnthropicAPIError(APIError):
    """Claude API固有のエラー"""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None
    ) -> None:
        super().__init__(message, "Anthropic API", status_code, response_body)


class ValidationError(PartnerRefinerError):
    """入力検証エラー"""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"検証エラー: {field}", message)
        self.field = field


class MatchingError(PartnerRefinerError):
    """マッチング処理エラー"""
    pass


class DataFormatError(PartnerRefinerError):
    """データ形式エラー（CSV解析失敗など）"""

    def __init__(self, message: str, file_path: str | None = None) -> None:
        super().__init__(message, file_path)
        self.file_path = file_path


class CacheError(PartnerRefinerError):
    """キャッシュ関連エラー"""
    pass


def format_error_for_user(error: Exception) -> str:
    """
    ユーザー向けのエラーメッセージをフォーマットする

    Args:
        error: 例外オブジェクト

    Returns:
        ユーザー向けのエラーメッセージ
    """
    if isinstance(error, ConfigurationError):
        return f"❌ 設定エラー: {error.message}\n   解決方法: 必要な環境変数を設定してください"

    if isinstance(error, FreeeAPIError):
        msg = f"❌ freee API エラー: {error.message}"
        if error.status_code == 401:
            msg += "\n   解決方法: FREEE_ACCESS_TOKEN を確認してください"
        elif error.status_code == 403:
            msg += "\n   解決方法: APIアクセス権限を確認してください"
        elif error.status_code == 429:
            msg += "\n   解決方法: しばらく待ってから再実行してください"
        return msg

    if isinstance(error, AnthropicAPIError):
        msg = f"❌ Claude API エラー: {error.message}"
        if error.status_code == 401:
            msg += "\n   解決方法: ANTHROPIC_API_KEY を確認してください"
        elif error.status_code == 429:
            msg += "\n   解決方法: APIレート制限です。しばらく待ってください"
        return msg

    if isinstance(error, ValidationError):
        return f"❌ 入力エラー ({error.field}): {error.details}"

    if isinstance(error, DataFormatError):
        msg = f"❌ データ形式エラー: {error.message}"
        if error.file_path:
            msg += f"\n   ファイル: {error.file_path}"
        return msg

    if isinstance(error, PartnerRefinerError):
        return f"❌ エラー: {error}"

    # 想定外のエラー
    return f"❌ 予期しないエラー: {type(error).__name__}: {error}"
