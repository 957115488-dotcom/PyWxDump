"""微信导入 API（首次触发初始化下载）。

首次点击“导入微信消息”时，从指定 GitHub 仓库拉取初始化资源，
完成后写入本地标记；后续请求直接返回已完成状态。
"""

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pywxdump.downloader import ScriptDownloader

router = APIRouter(prefix="/api/import", tags=["import"])

_DEFAULT_FILE_PATH = "pywxdump/config.py"
_DEFAULT_BRANCH = "master"


class ImportRequestResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    initialized: bool


def _state_path(request: Request) -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "wx_import_state.json"


def _is_initialized(state_path: Path) -> bool:
    if not state_path.exists():
        return False
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return bool(data.get("initialized"))
    except Exception:
        return False


def _mark_initialized(state_path: Path, record: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


@router.post("/wx-request", response_model=ImportRequestResponse)
async def request_wx_import(request: Request) -> ImportRequestResponse:
    now = datetime.now(timezone(timedelta(hours=8)))
    ts = now.isoformat()
    state_path = _state_path(request)

    if _is_initialized(state_path):
        return ImportRequestResponse(
            status="ok",
            message="初始化已完成，后续无需重复获取。",
            timestamp=ts,
            initialized=True,
        )

    downloader = ScriptDownloader()
    result = await downloader.download_script(file_path=_DEFAULT_FILE_PATH, branch=_DEFAULT_BRANCH)

    if not result.success:
        return JSONResponse(
            content={
                "status": "error",
                "message": f"首次初始化失败：{result.error}",
                "timestamp": ts,
                "initialized": False,
            },
            status_code=502,
        )

    record = {
        "initialized": True,
        "initialized_at": ts,
        "repo": downloader.repo,
        "file_path": _DEFAULT_FILE_PATH,
        "branch": _DEFAULT_BRANCH,
        "local_path": result.local_path,
        "script_info": result.script_info.to_dict() if result.script_info else None,
        "ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
    }
    _mark_initialized(state_path, record)

    return ImportRequestResponse(
        status="ok",
        message="首次初始化完成，后续点击将不再重复获取。",
        timestamp=ts,
        initialized=True,
    )


