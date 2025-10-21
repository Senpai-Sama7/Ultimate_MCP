"""Secure code execution tool with process pool isolation."""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import subprocess
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel, Field

from ..database.models import ExecutionResult
from ..database.neo4j_client import Neo4jClient
from ..utils.enhanced_security import ensure_safe_python
from ..utils.validation import ensure_supported_language

logger = logging.getLogger(__name__)


class ExecutionRequest(BaseModel):
    code: str = Field(..., description="Code snippet to execute.")
    language: str = Field(default="python", description="Language of the provided code.")
    timeout_seconds: float = Field(default=8.0, ge=0.5, le=60.0)


class ExecutionResponse(BaseModel):
    id: str
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float


def _execute_python_static(request: ExecutionRequest) -> ExecutionResult:
    """Static function for process pool execution (must be picklable).

    Args:
        request: Execution request

    Returns:
        Execution result
    """
    with TemporaryDirectory(prefix="ultimate_mcp_exec_") as tmp:
        script_path = Path(tmp) / "snippet.py"
        script_path.write_text(request.code, encoding="utf-8")

        cmd = [sys.executable, str(script_path)]
        start = time.perf_counter()
        try:
            completed = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                check=False,
                cwd=tmp,
            )
            duration = time.perf_counter() - start

            return ExecutionResult(
                id=str(uuid.uuid4()),
                language="python",
                return_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired:
            duration = time.perf_counter() - start
            return ExecutionResult(
                id=str(uuid.uuid4()),
                language="python",
                return_code=-1,
                stdout="",
                stderr=f"Execution timed out after {request.timeout_seconds}s",
                duration_seconds=duration,
            )
        except Exception as e:
            duration = time.perf_counter() - start
            return ExecutionResult(
                id=str(uuid.uuid4()),
                language="python",
                return_code=-1,
                stdout="",
                stderr=f"Execution error: {str(e)}",
                duration_seconds=duration,
            )


class ExecutionTool:
    """Secure code execution tool with process pool isolation.

    Uses ProcessPoolExecutor instead of threadpool for better isolation
    and performance under high concurrency.
    """

    def __init__(
        self,
        neo4j: Neo4jClient,
        max_workers: int | None = None,
        max_concurrent: int | None = None,
    ) -> None:
        """Initialize execution tool with process pool.

        Args:
            neo4j: Neo4j client for result persistence
            max_workers: Max worker processes (default: min(cpu_count, 4))
            max_concurrent: Max concurrent executions (default: max_workers * 2)
        """
        self._neo4j = neo4j

        # Configure process pool
        if max_workers is None:
            cpu_count = multiprocessing.cpu_count()
            max_workers = min(cpu_count, 4)  # Limit to 4 even on large machines

        if max_concurrent is None:
            max_concurrent = max_workers * 2  # Allow some queueing

        # Create dedicated process pool for isolation
        self._executor = ProcessPoolExecutor(
            max_workers=max_workers,
            mp_context=multiprocessing.get_context('spawn')  # Force spawn for safety
        )
        self._semaphore = asyncio.Semaphore(max_concurrent)

        logger.info(
            "Execution tool initialized with process pool",
            extra={
                "max_workers": max_workers,
                "max_concurrent": max_concurrent,
            }
        )

    async def run(self, request: ExecutionRequest) -> ExecutionResponse:
        """Execute code with process pool isolation.

        Features:
        - Process-level isolation (not just threads)
        - Concurrency limiting via semaphore
        - Automatic cleanup on completion
        - Timeout enforcement

        Args:
            request: Execution request with code and configuration

        Returns:
            Execution response with results

        Raises:
            ValueError: If language is unsupported or code is unsafe
        """
        ensure_supported_language(request.language)
        if request.language != "python":
            raise ValueError("Execution tool currently supports only Python code.")

        ensure_safe_python(request.code)

        # Use semaphore to limit concurrent executions
        async with self._semaphore:
            loop = asyncio.get_event_loop()
            try:
                # Execute in separate process via executor
                result = await loop.run_in_executor(
                    self._executor,
                    _execute_python_static,
                    request,
                )
            except Exception as e:
                logger.error(f"Code execution failed: {e}", exc_info=True)
                # Return error result instead of raising
                result = ExecutionResult(
                    id=str(uuid.uuid4()),
                    language="python",
                    return_code=-1,
                    stdout="",
                    stderr=f"Execution error: {str(e)}",
                    duration_seconds=0.0,
                )

        await self._persist(result)

        return ExecutionResponse(
            id=result.id,
            return_code=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_seconds=result.duration_seconds,
        )

    async def shutdown(self) -> None:
        """Gracefully shutdown the process pool."""
        logger.info("Shutting down execution tool process pool")
        self._executor.shutdown(wait=True)
        logger.info("Execution tool shutdown complete")

    async def _persist(self, result: ExecutionResult) -> None:
        await self._neo4j.execute_write(
            """
            MERGE (r:ExecutionResult {id: $id})
            SET r += {
                language: $language,
                return_code: $return_code,
                stdout: $stdout,
                stderr: $stderr,
                duration_seconds: $duration_seconds,
                created_at: datetime($created_at)
            }
            """,
            {
                "id": result.id,
                "language": result.language,
                "return_code": result.return_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_seconds": result.duration_seconds,
                "created_at": result.created_at.isoformat(),
            },
        )


__all__ = ["ExecutionTool", "ExecutionRequest", "ExecutionResponse"]
