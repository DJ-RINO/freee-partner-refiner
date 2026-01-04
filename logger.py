"""
ロギングモジュール

プロジェクト共通のロガー設定を提供する。
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def get_logger(
    name: str,
    level: int = logging.INFO,
    log_file: str | None = None,
    log_dir: str | None = None
) -> logging.Logger:
    """
    ロガーを取得する

    Args:
        name: ロガー名（通常は__name__）
        level: ログレベル
        log_file: ログファイル名（省略時は自動生成）
        log_dir: ログディレクトリ（省略時はlogsディレクトリ）

    Returns:
        設定済みのロガー
    """
    logger = logging.getLogger(name)

    # 既に設定済みの場合は返す
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # フォーマッター
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # コンソールハンドラ
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ファイルハンドラ（オプション）
    if log_dir or log_file:
        if log_dir:
            log_path = Path(log_dir)
        else:
            log_path = Path(__file__).parent / "logs"

        log_path.mkdir(parents=True, exist_ok=True)

        if not log_file:
            timestamp = datetime.now().strftime("%Y%m%d")
            log_file = f"{name}_{timestamp}.log"

        file_handler = logging.FileHandler(
            log_path / log_file,
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def setup_file_logging(log_dir: str | None = None) -> Path:
    """
    ファイルロギングをセットアップする

    Args:
        log_dir: ログディレクトリ

    Returns:
        ログディレクトリのPath
    """
    if log_dir:
        log_path = Path(log_dir)
    else:
        log_path = Path(__file__).parent / "logs"

    log_path.mkdir(parents=True, exist_ok=True)
    return log_path


# プロジェクト共通のログレベル設定
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL
}


def parse_log_level(level_str: str) -> int:
    """
    ログレベル文字列をパースする

    Args:
        level_str: "debug", "info", "warning", "error", "critical"

    Returns:
        logging.LEVEL 定数
    """
    return LOG_LEVELS.get(level_str.lower(), logging.INFO)
