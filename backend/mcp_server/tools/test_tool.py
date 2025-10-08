"""Test execution tool."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel, Field

from ..database.models import TestResult
from ..database.neo4j_client import Neo4jClient
from ..utils.security import ensure_safe_python
from ..utils.validation import ensure_supported_language


class TestRequest(BaseModel):
    code: str = Field(..., description="Test module or function definitions to execute.")
    language: str = Field(default="python", description="Language for the supplied tests.")
    test_framework: str = Field(default="pytest", description="Test framework identifier.")
    timeout_seconds: float = Field(default=15.0, ge=1.0, le=120.0)


class TestResponse(BaseModel):
    id: str
    framework: str
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float


class TestTool:
    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    async def run(self, request: TestRequest) -> TestResponse:
        ensure_supported_language(request.language)
        if request.test_framework.lower() != "pytest":
            raise ValueError("Only pytest is currently supported for test execution.")

        ensure_safe_python(request.code)
        result = await asyncio.to_thread(self._execute_pytest, request)
        await self._persist(result)

        return TestResponse(
            id=result.id,
            framework=result.framework,
            return_code=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_seconds=result.duration_seconds,
        )

    def _execute_pytest(self, request: TestRequest) -> TestResult:
        with TemporaryDirectory(prefix="ultimate_mcp_tests_") as tmp:
            test_path = Path(tmp) / "test_generated.py"
            test_path.write_text(request.code, encoding="utf-8")

            env = os.environ.copy()
            env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

            cmd = [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                str(test_path),
                "--disable-warnings",
                "--maxfail=1",
            ]

            start = time.perf_counter()
            completed = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                env=env,
                cwd=tmp,
                timeout=request.timeout_seconds,
                check=False,
                text=True,
            )
            duration = time.perf_counter() - start

        return TestResult(
            id=str(uuid.uuid4()),
            framework="pytest",
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=duration,
        )

    async def _persist(self, result: TestResult) -> None:
        await self._neo4j.execute_write(
            """
            MERGE (r:TestResult {id: $id})
            SET r += {
                framework: $framework,
                return_code: $return_code,
                stdout: $stdout,
                stderr: $stderr,
                duration_seconds: $duration_seconds,
                created_at: datetime($created_at)
            }
            """,
            {
                "id": result.id,
                "framework": result.framework,
                "return_code": result.return_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_seconds": result.duration_seconds,
                "created_at": result.created_at.isoformat(),
            },
        )


__all__ = ["TestTool", "TestRequest", "TestResponse"]
