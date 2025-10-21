"""Async execution tool with non-blocking subprocess calls."""

from __future__ import annotations

import asyncio
import sys
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from pydantic import BaseModel, Field

from .exec_tool import ExecutionRequest, ExecutionResponse, ExecutionResult


class AsyncExecutionTool:
    """Async code execution tool with non-blocking subprocess calls."""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run(self, request: ExecutionRequest) -> ExecutionResponse:
        """Execute code asynchronously without blocking the event loop."""
        async with self._semaphore:
            if request.language.lower() == "python":
                result = await self._execute_python_async(request)
            else:
                raise ValueError(f"Unsupported language: {request.language}")
            
            return ExecutionResponse(
                id=result.id,
                language=result.language,
                return_code=result.return_code,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=result.duration_seconds,
            )
    
    async def _execute_python_async(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute Python code using async subprocess."""
        with TemporaryDirectory(prefix="ultimate_mcp_exec_") as tmp:
            script_path = Path(tmp) / "snippet.py"
            script_path.write_text(request.code, encoding="utf-8")
            
            cmd = [sys.executable, str(script_path)]
            start = time.perf_counter()
            
            try:
                # Use asyncio.create_subprocess_exec for non-blocking execution
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmp,
                )
                
                # Wait for completion with timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=request.timeout_seconds
                )
                
                duration = time.perf_counter() - start
                
                return ExecutionResult(
                    id=str(uuid.uuid4()),
                    language="python",
                    return_code=process.returncode or 0,
                    stdout=stdout.decode("utf-8") if stdout else "",
                    stderr=stderr.decode("utf-8") if stderr else "",
                    duration_seconds=duration,
                )
                
            except asyncio.TimeoutError:
                # Kill the process if it times out
                if process.returncode is None:
                    process.kill()
                    await process.wait()
                
                duration = time.perf_counter() - start
                return ExecutionResult(
                    id=str(uuid.uuid4()),
                    language="python",
                    return_code=-1,
                    stdout="",
                    stderr=f"Execution timed out after {request.timeout_seconds} seconds",
                    duration_seconds=duration,
                )


__all__ = ["AsyncExecutionTool"]
