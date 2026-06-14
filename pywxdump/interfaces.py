"""PyWxDump 接口定义（Protocol）

定义核心组件的抽象接口，支持依赖注入和测试替换。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pywxdump.sandbox import SandboxResult


@runtime_checkable
class IDownloader(Protocol):
    """社区脚本下载器接口"""

    async def download_script(self, file_path: str, branch: str) -> Any:
        """下载脚本到本地缓存，返回 DownloadResult"""
        ...

    async def verify_cached(self, file_path: str) -> bool:
        """验证缓存文件的 SHA256 完整性"""
        ...

    def get_cached_path(self, file_path: str) -> Path | None:
        """获取缓存文件路径"""
        ...

    def get_cache_info(self) -> dict:
        """获取缓存信息"""
        ...


@runtime_checkable
class ISandboxRunner(Protocol):
    """沙盒运行器接口"""

    async def run_script(
        self,
        script_path: str | Path,
        args: list[str] | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> SandboxResult:
        """在沙盒中运行指定脚本"""
        ...

    async def run_code(
        self,
        code: str,
        env_overrides: dict[str, str] | None = None,
    ) -> SandboxResult:
        """在沙盒中运行代码字符串"""
        ...


@runtime_checkable
class IComplianceManager(Protocol):
    """合规确认管理器接口"""

    def get_compliance_text(self) -> dict[str, Any]:
        """获取合规文案和等待时间"""
        ...

    async def process_confirmation(
        self, ip: str, user_agent: str,
    ) -> Any:
        """处理合规确认请求"""
        ...

    def is_confirmed(self, ip: str) -> bool:
        """检查指定 IP 是否已确认"""
        ...