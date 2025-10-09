"""Secure code execution tool."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel, Field

from ..database.models import ExecutionResult
from ..database.neo4j_client import Neo4jClient
from ..utils.enhanced_security import ensure_safe_python
from ..utils.validation import ensure_supported_language


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


class ExecutionTool:
    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    async def run(self, request: ExecutionRequest) -> ExecutionResponse:
        ensure_supported_language(request.language)
        if request.language != "python":
            raise ValueError("Execution tool currently supports only Python code.")

        ensure_safe_python(request.code)
        result = await asyncio.to_thread(self._execute_python, request)
        await self._persist(result)

        return ExecutionResponse(
            id=result.id,
            return_code=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_seconds=result.duration_seconds,
        )

    def _execute_python(self, request: ExecutionRequest) -> ExecutionResult:
        with TemporaryDirectory(prefix="ultimate_mcp_exec_") as tmp:
            script_path = Path(tmp) / "snippet.py"
            script_path.write_text(request.code, encoding="utf-8")

            cmd = [sys.executable, str(script_path)]
            start = time.perf_counter()
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
