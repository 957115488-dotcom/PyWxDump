"""PyWxDump 妯″潡閰嶇疆 鈥?鏀寔鐜鍙橀噺瑕嗙洊"""

from __future__ import annotations

import os
from pathlib import Path

# GitHub 浠撳簱
DEFAULT_REPO: str = os.getenv("PYWXDUMP_REPO", "957115488-dotcom/PyWxDump")
GITHUB_API_BASE: str = os.getenv("PYWXDUMP_API_BASE", "https://api.github.com")
GITHUB_RAW_BASE: str = os.getenv("PYWXDUMP_RAW_BASE", "https://raw.githubusercontent.com")

# 涓嬭浇
DOWNLOAD_TIMEOUT: float = float(os.getenv("PYWXDUMP_DOWNLOAD_TIMEOUT", "60"))

# 缂撳瓨
CACHE_DIR: str = os.getenv(
    "PYWXDUMP_CACHE_DIR",
    str(Path.home() / ".dustmirror" / "pywxdump_cache"),
)

# 鍚堣纭
CONFIRM_WAIT_SECONDS: int = int(os.getenv("PYWXDUMP_CONFIRM_WAIT", "3"))
COMPLIANCE_LOG_DIR: str = os.getenv(
    "PYWXDUMP_COMPLIANCE_LOG_DIR",
    str(Path.home() / ".dustmirror" / "compliance_logs"),
)

# 娌欑洅
SANDBOX_TIMEOUT: float = float(os.getenv("PYWXDUMP_SANDBOX_TIMEOUT", "300"))
SANDBOX_LOG_FILE: str = os.getenv("PYWXDUMP_SANDBOX_LOG", "sandbox.log")
