"""
合规确认流程模块
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from pywxdump.config import CONFIRM_WAIT_SECONDS, COMPLIANCE_LOG_DIR

logger = logging.getLogger("pywxdump.compliance")

COMPLIANCE_TEXT = (
    "由于合规要求，本软件不内置特定应用的解密模块。\n"
    "是否允许本软件从 GitHub 社区（如 PyWxDump 等仓库）\n"
    "临时下载最新的开源提取脚本并在本地沙盒中运行？"
)


@dataclass
class ComplianceConfirm:
    confirmed: bool
    confirmed_at: str = ""
    ip: str = "unknown"
    user_agent: str = "unknown"
    wait_seconds: int = CONFIRM_WAIT_SECONDS

    def to_dict(self) -> dict[str, Any]:
        return {
            "confirmed": self.confirmed,
            "confirmed_at": self.confirmed_at,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "wait_seconds": self.wait_seconds,
        }


class ComplianceManager:
    def __init__(self, log_dir: str | Path | None = None, wait_seconds: int | None = None) -> None:
        self._log_dir = Path(log_dir) if log_dir else Path(COMPLIANCE_LOG_DIR)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._wait_seconds = wait_seconds if wait_seconds is not None else CONFIRM_WAIT_SECONDS
        self._confirmations: dict[str, ComplianceConfirm] = {}

    def get_compliance_text(self) -> dict[str, Any]:
        return {"text": COMPLIANCE_TEXT, "wait_seconds": self._wait_seconds, "version": "1.0"}

    async def process_confirmation(self, ip: str = "unknown", user_agent: str = "unknown") -> ComplianceConfirm:
        logger.info("合规确认请求开始 | IP=%s | 等待=%ds", ip, self._wait_seconds)
        await asyncio.sleep(self._wait_seconds)
        now = datetime.now(timezone(timedelta(hours=8)))
        confirm = ComplianceConfirm(confirmed=True, confirmed_at=now.isoformat(), ip=ip, user_agent=user_agent, wait_seconds=self._wait_seconds)
        self._confirmations[ip] = confirm
        self._log_confirmation(confirm)
        logger.info("合规确认完成 | IP=%s | 时间=%s", ip, confirm.confirmed_at)
        return confirm

    def is_confirmed(self, ip: str) -> bool:
        return ip in self._confirmations

    def _log_confirmation(self, confirm: ComplianceConfirm) -> None:
        log_file = self._log_dir / "confirmations.jsonl"
        try:
            with log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(confirm.to_dict(), ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("写入合规确认日志失败: %s", exc)
