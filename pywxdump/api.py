"""
PyWxDump API 路由模块（工厂函数模式）

提供微信解密导出相关的 REST API 端点：
- GET  /api/pywxdump/compliance-text  获取合规文案
- POST /api/pywxdump/confirm          提交合规确认（含3秒强制等待）
- POST /api/pywxdump/run              下载并运行社区脚本
- GET  /api/pywxdump/status            查询运行状态

支持依赖注入：通过 create_router() 传入自定义实现。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from pywxdump.interfaces import IComplianceManager, IDownloader, ISandboxRunner
from pywxdump.compliance import ComplianceManager
from pywxdump.downloader import ScriptDownloader, DownloadResult
from pywxdump.sandbox import SandboxRunner, SandboxLevel, SandboxResult

logger = logging.getLogger("pywxdump.api")


# ── 请求/响应模型 ────────────────────────────────────

class ConfirmRequest(BaseModel):
    acknowledged: bool = True


class RunRequest(BaseModel):
    file_path: str = "wxdump/wx_dump.py"
    branch: str = "main"
    args: list[str] | None = None


class ComplianceTextResponse(BaseModel):
    text: str
    wait_seconds: int
    version: str


class StatusResponse(BaseModel):
    running: bool
    last_result: dict | None
    last_error: str | None
    cache_info: dict


# ── 运行状态（实例级而非模块级全局） ──────────────────

class _RunState:
    """线程安全的运行状态"""
    __slots__ = ("running", "last_result", "last_error")

    def __init__(self) -> None:
        self.running = False
        self.last_result: dict | None = None
        self.last_error: str | None = None

    def reset(self) -> None:
        self.running = False
        self.last_result = None
        self.last_error = None


# ── 工厂函数 ──────────────────────────────────────────

def create_router(
    compliance: IComplianceManager | None = None,
    downloader: IDownloader | None = None,
    sandbox: ISandboxRunner | None = None,
) -> APIRouter:
    """
    创建 PyWxDump API 路由（支持依赖注入）

    Args:
        compliance: 合规确认管理器（默认 ComplianceManager）
        downloader: 脚本下载器（默认 ScriptDownloader）
        sandbox: 沙盒运行器（默认 SandboxRunner）

    Returns:
        配置好的 APIRouter
    """
    _compliance: IComplianceManager = compliance or ComplianceManager()
    _downloader: IDownloader = downloader or ScriptDownloader()
    _sandbox: ISandboxRunner = sandbox or SandboxRunner(level=SandboxLevel.BASIC)
    _state = _RunState()

    router = APIRouter(prefix="/api/pywxdump", tags=["pywxdump"])

    @router.get("/compliance-text", response_model=ComplianceTextResponse)
    async def get_compliance_text() -> ComplianceTextResponse:
        """获取合规确认文案和等待时间"""
        data = _compliance.get_compliance_text()
        return ComplianceTextResponse(**data)

    @router.post("/confirm")
    async def confirm_compliance(request: Request, body: ConfirmRequest | None = None) -> dict[str, Any]:
        """提交合规确认（强制等待3秒）"""
        ip = request.client.host if request.client else "unknown"
        ua = request.headers.get("user-agent", "unknown")

        if body and not body.acknowledged:
            raise HTTPException(status_code=400, detail="必须确认同意合规条款")

        confirm = await _compliance.process_confirmation(ip=ip, user_agent=ua)
        return {"status": "confirmed", "message": "合规确认已完成", "data": confirm.to_dict()}

    @router.post("/run")
    async def run_community_script(request: Request, body: RunRequest | None = None) -> dict[str, Any]:
        """下载并运行社区脚本（需先通过合规确认）"""
        ip = request.client.host if request.client else "unknown"

        if not _compliance.is_confirmed(ip):
            raise HTTPException(status_code=403, detail="请先完成合规确认（POST /api/pywxdump/confirm）")

        if _state.running:
            raise HTTPException(status_code=409, detail="已有脚本正在运行中")

        file_path = body.file_path if body else "wxdump/wx_dump.py"
        branch = body.branch if body else "main"
        args = body.args if body else None

        _state.running = True
        _state.last_error = None

        try:
            logger.info("开始下载社区脚本: %s (branch: %s)", file_path, branch)
            dl_result: DownloadResult = await _downloader.download_script(file_path=file_path, branch=branch)
            if not dl_result.success:
                _state.last_error = dl_result.error
                raise HTTPException(status_code=502, detail=f"脚本下载失败: {dl_result.error}")

            if not await _downloader.verify_cached(file_path):
                _state.last_error = "SHA256 校验失败"
                raise HTTPException(status_code=502, detail="脚本完整性校验失败")

            logger.info("在沙盒中运行脚本: %s", dl_result.local_path)
            run_result: SandboxResult = await _sandbox.run_script(dl_result.local_path, args=args)
            _state.last_result = run_result.to_dict()

            if not run_result.success:
                _state.last_error = run_result.error
                raise HTTPException(status_code=500, detail=f"脚本运行失败: {run_result.error}")

            return {
                "status": "success", "message": "社区脚本已成功执行",
                "download": dl_result.to_dict(), "execution": run_result.to_dict(),
            }

        except HTTPException:
            raise
        except Exception as exc:
            _state.last_error = str(exc)
            logger.exception("运行社区脚本异常: %s", exc)
            raise HTTPException(status_code=500, detail=f"内部错误: {exc}")
        finally:
            _state.running = False

    @router.get("/status", response_model=StatusResponse)
    async def get_status() -> StatusResponse:
        """查询运行状态和缓存信息"""
        return StatusResponse(
            running=_state.running,
            last_result=_state.last_result,
            last_error=_state.last_error,
            cache_info=_downloader.get_cache_info(),
        )

    return router


# 默认路由实例（向后兼容）
router = create_router()