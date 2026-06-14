"""
社区脚本下载器模块

从 GitHub 下载最新社区脚本（如 PyWxDump），
支持 SHA256 校验、版本检查、本地缓存。
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from pywxdump.config import (
    DEFAULT_REPO, GITHUB_API_BASE, GITHUB_RAW_BASE,
    DOWNLOAD_TIMEOUT, CACHE_DIR,
)

logger = logging.getLogger("pywxdump.downloader")


@dataclass
class ScriptInfo:
    """脚本信息"""
    name: str
    version: str
    sha256: str
    download_url: str
    file_size: int = 0
    downloaded_at: str = ""
    repo: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "version": self.version,
            "sha256": self.sha256, "download_url": self.download_url,
            "file_size": self.file_size, "downloaded_at": self.downloaded_at,
            "repo": self.repo,
        }


@dataclass
class DownloadResult:
    """下载结果"""
    success: bool
    script_info: ScriptInfo | None = None
    local_path: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"success": self.success, "local_path": self.local_path, "error": self.error}
        if self.script_info:
            result["script_info"] = self.script_info.to_dict()
        return result


class ScriptDownloader:
    """
    社区脚本下载器

    从 GitHub 仓库下载最新脚本到本地缓存目录，
    支持 SHA256 完整性校验和版本管理。
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        repo: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.repo = repo or DEFAULT_REPO
        self.timeout = timeout or DOWNLOAD_TIMEOUT
        self.cache_dir = Path(cache_dir) if cache_dir else Path(CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.cache_dir / "manifest.json"
        self._manifest: dict[str, Any] = self._load_manifest()

    def _load_manifest(self) -> dict[str, Any]:
        if self._manifest_path.exists():
            try:
                return json.loads(self._manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("加载清单文件失败: %s", exc)
        return {"scripts": {}, "last_check": None}

    def _save_manifest(self) -> None:
        try:
            self._manifest_path.write_text(
                json.dumps(self._manifest, ensure_ascii=False, indent=2), encoding="utf-8",
            )
        except OSError as exc:
            logger.error("保存清单文件失败: %s", exc)

    async def check_latest_version(self) -> dict[str, Any] | None:
        """检查 GitHub 仓库最新版本信息"""
        url = f"{GITHUB_API_BASE}/repos/{self.repo}/releases/latest"
        logger.info("检查最新版本: %s", url)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "DustMirror-PyWxDump"})
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info("最新版本: %s (tag: %s)", data.get("name", ""), data.get("tag_name", ""))
                    return data
                logger.warning("获取版本信息失败: HTTP %d", resp.status_code)
                return None
            except httpx.HTTPError as exc:
                logger.error("版本检查网络错误: %s", exc)
                return None

    async def download_script(self, file_path: str = "wxdump/wx_dump.py", branch: str = "main") -> DownloadResult:
        """下载指定仓库文件到本地缓存"""
        raw_url = f"{GITHUB_RAW_BASE}/{self.repo}/{branch}/{file_path}"
        logger.info("开始下载脚本: %s", raw_url)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(raw_url, headers={"User-Agent": "DustMirror-PyWxDump"}, follow_redirects=True)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error("下载失败: HTTP %d", exc.response.status_code)
                return DownloadResult(success=False, error=f"下载失败: HTTP {exc.response.status_code}")
            except httpx.HTTPError as exc:
                logger.error("下载网络错误: %s", exc)
                return DownloadResult(success=False, error=f"下载网络错误: {exc}")

            content = resp.content
            file_hash = hashlib.sha256(content).hexdigest()

            local_file = self.cache_dir / Path(file_path).name
            local_file.write_bytes(content)

            release_info = await self.check_latest_version()
            version = release_info.get("tag_name", branch) if release_info else branch

            script_info = ScriptInfo(
                name=Path(file_path).name, version=version, sha256=file_hash,
                download_url=raw_url, file_size=len(content),
                downloaded_at=datetime.now(timezone.utc).isoformat(), repo=self.repo,
            )

            self._manifest["scripts"][file_path] = script_info.to_dict()
            self._manifest["last_check"] = datetime.now(timezone.utc).isoformat()
            self._save_manifest()

            logger.info("下载完成 | 文件=%s | 大小=%d 字节 | SHA256=%s", local_file, len(content), file_hash[:16])
            return DownloadResult(success=True, script_info=script_info, local_path=str(local_file))

    async def verify_cached(self, file_path: str) -> bool:
        """验证缓存文件的 SHA256 完整性"""
        entry = self._manifest.get("scripts", {}).get(file_path)
        if not entry:
            return False
        local_file = self.cache_dir / Path(file_path).name
        if not local_file.exists():
            return False
        actual_hash = hashlib.sha256(local_file.read_bytes()).hexdigest()
        expected_hash = entry.get("sha256", "")
        if actual_hash != expected_hash:
            logger.warning("SHA256 校验失败 | 文件=%s | 期望=%s | 实际=%s", file_path, expected_hash[:16], actual_hash[:16])
            return False
        logger.info("SHA256 校验通过: %s", file_path)
        return True

    def get_cached_path(self, file_path: str) -> Path | None:
        """获取缓存文件路径（如果存在且有效）"""
        local_file = self.cache_dir / Path(file_path).name
        return local_file if local_file.exists() else None

    def get_cache_info(self) -> dict[str, Any]:
        """获取缓存信息"""
        return {
            "cache_dir": str(self.cache_dir),
            "manifest": self._manifest,
            "cached_files": [f.name for f in self.cache_dir.iterdir() if f.is_file()],
        }
