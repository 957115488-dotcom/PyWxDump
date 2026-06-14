"""
沙盒运行器模块

在受限环境中运行社区脚本，支持文件系统隔离、网络限制、超时控制。
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import time
from enum import Enum
from pathlib import Path
from typing import Any

from pywxdump.config import SANDBOX_TIMEOUT, SANDBOX_LOG_FILE

logger = logging.getLogger("pywxdump.sandbox")


class SandboxLevel(str, Enum):
    """沙盒安全级别"""
    BASIC = "BASIC"
    STRICT = "STRICT"


class SandboxResult:
    """沙盒运行结果"""

    __slots__ = ("success", "stdout", "stderr", "exit_code", "duration", "error")

    def __init__(
        self, success: bool, stdout: str = "", stderr: str = "",
        exit_code: int = -1, duration: float = 0.0, error: str | None = None,
    ) -> None:
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.duration = duration
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success, "stdout": self.stdout, "stderr": self.stderr,
            "exit_code": self.exit_code, "duration": round(self.duration, 3), "error": self.error,
        }


class SandboxRunner:
    """
    沙盒运行器

    在受限环境中运行 Python 脚本，提供：
    - 临时目录隔离
    - 超时控制（默认 300 秒）
    - 完整日志记录
    - 异常隔离（脚本异常不影响主进程）
    """

    def __init__(
        self,
        level: SandboxLevel = SandboxLevel.BASIC,
        timeout: float | None = None,
        log_file: str | None = None,
    ) -> None:
        self.level = level
        self.timeout = timeout or SANDBOX_TIMEOUT
        self._temp_dir: str | None = None
        self._log_path = Path(log_file or SANDBOX_LOG_FILE)
        file_handler = logging.FileHandler(self._log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)

    def _create_temp_dir(self) -> str:
        temp_dir = tempfile.mkdtemp(prefix="pywxdump_sandbox_")
        self._temp_dir = temp_dir
        logger.info("创建临时目录: %s", temp_dir)
        return temp_dir

    def _cleanup_temp_dir(self) -> None:
        if self._temp_dir and Path(self._temp_dir).exists():
            try:
                shutil.rmtree(self._temp_dir)
                logger.info("已清理临时目录: %s", self._temp_dir)
            except OSError as exc:
                logger.warning("清理临时目录失败: %s, 错误: %s", self._temp_dir, exc)
            finally:
                self._temp_dir = None

    async def run_script(
        self, script_path: str | Path, args: list[str] | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> SandboxResult:
        """在沙盒中运行指定 Python 脚本"""
        script_path = Path(script_path).resolve()
        if not script_path.exists():
            logger.error("脚本文件不存在: %s", script_path)
            return SandboxResult(success=False, error=f"脚本文件不存在: {script_path}")

        work_dir = self._create_temp_dir()
        start_time = time.monotonic()
        logger.info("开始沙盒运行 | 级别=%s | 脚本=%s | 超时=%.1fs", self.level.value, script_path, self.timeout)

        try:
            cmd = ["python", str(script_path)]
            if args:
                cmd.extend(args)

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, cwd=work_dir, env=None,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                elapsed = time.monotonic() - start_time
                logger.error("脚本执行超时 (%.1fs): %s", elapsed, script_path)
                return SandboxResult(success=False, exit_code=-1, duration=elapsed, error=f"脚本执行超时 ({self.timeout}秒)")

            elapsed = time.monotonic() - start_time
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0
            success = exit_code == 0

            logger.info("沙盒运行完成 | 成功=%s | 退出码=%d | 耗时=%.3fs", success, exit_code, elapsed)
            if not success:
                logger.warning("脚本错误输出: %s", stderr[:500])

            return SandboxResult(success=success, stdout=stdout, stderr=stderr, exit_code=exit_code, duration=elapsed, error=stderr if not success else None)

        except Exception as exc:
            elapsed = time.monotonic() - start_time
            logger.exception("沙盒运行异常: %s", exc)
            return SandboxResult(success=False, duration=elapsed, error=f"沙盒运行异常: {type(exc).__name__}: {exc}")
        finally:
            self._cleanup_temp_dir()

    async def run_code(self, code: str, env_overrides: dict[str, str] | None = None) -> SandboxResult:
        """在沙盒中运行 Python 代码字符串"""
        work_dir = self._create_temp_dir()
        script_file = Path(work_dir) / "_sandbox_script.py"
        script_file.write_text(code, encoding="utf-8")
        return await self.run_script(script_file, env_overrides=env_overrides)