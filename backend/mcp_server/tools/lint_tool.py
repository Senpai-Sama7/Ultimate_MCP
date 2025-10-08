"""Linting tool implementation."""

from __future__ import annotations

import ast
import asyncio
import hashlib
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, Field

from ..database.models import LintResult
from ..database.neo4j_client import Neo4jClient
from ..utils.validation import ensure_supported_language


@dataclass(slots=True)
class _LinterOutcome:
    exit_code: int
    output: str


class LintRequest(BaseModel):
    code: str = Field(..., description="Source code to lint.")
    language: str = Field(default="python", description="Programming language identifier.")


class LintResponse(BaseModel):
    id: str
    code_hash: str
    functions: list[str]
    classes: list[str]
    imports: list[str]
    complexity: float
    linter_exit_code: int
    linter_output: str


class LintTool:
    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    async def run(self, request: LintRequest) -> LintResponse:
        ensure_supported_language(request.language)
        tree = ast.parse(request.code)
        functions = sorted(
            {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        )
        classes = sorted({node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)})
        imports = sorted(
            {
                alias.name.split(".")[0]
                for node in ast.walk(tree)
                for alias in getattr(node, "names", [])
                if isinstance(node, (ast.Import, ast.ImportFrom))
            }
        )
        complexity = self._estimate_complexity(tree)
        code_hash = hashlib.sha256(request.code.encode("utf-8")).hexdigest()

        outcome = await asyncio.to_thread(self._run_external_linter, request.code, request.language)
        record_id = str(uuid.uuid4())

        lint_result = LintResult(
            id=record_id,
            code_hash=code_hash,
            language=request.language,
            functions=functions,
            classes=classes,
            imports=imports,
            complexity=complexity,
            linter_exit_code=outcome.exit_code,
            linter_output=outcome.output,
        )
        await self._persist(lint_result)

        return LintResponse(
            id=lint_result.id,
            code_hash=lint_result.code_hash,
            functions=lint_result.functions,
            classes=lint_result.classes,
            imports=lint_result.imports,
            complexity=lint_result.complexity,
            linter_exit_code=lint_result.linter_exit_code,
            linter_output=lint_result.linter_output,
        )

    async def _persist(self, result: LintResult) -> None:
        payload = result.model_dump()
        await self._neo4j.execute_write(
            """
            MERGE (r:LintResult {id: $id})
            SET r += {
                code_hash: $code_hash,
                language: $language,
                functions: $functions,
                classes: $classes,
                imports: $imports,
                complexity: $complexity,
                linter_exit_code: $linter_exit_code,
                linter_output: $linter_output,
                created_at: datetime($created_at)
            }
            """,
            {**payload, "created_at": result.created_at.isoformat()},
        )

    def _run_external_linter(self, code: str, language: str) -> _LinterOutcome:
        if language != "python":
            return _LinterOutcome(0, "External linting unavailable for non-Python languages.")

        if shutil.which("ruff"):
            cmd = ["ruff", "check", "--quiet", "--stdin-filename", "snippet.py", "-"]
            completed = subprocess.run(  # noqa: S603
                cmd,
                input=code.encode("utf-8"),
                capture_output=True,
                check=False,
            )
            output = completed.stdout.decode() + completed.stderr.decode()
            return _LinterOutcome(completed.returncode, output.strip())

        if shutil.which("flake8"):
            with NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
                handle.write(code)
                temp_path = handle.name
            cmd = ["flake8", temp_path]
            completed = subprocess.run(  # noqa: S603
                cmd, capture_output=True, check=False
            )
            output = completed.stdout.decode() + completed.stderr.decode()
            return _LinterOutcome(completed.returncode, output.strip())

        return _LinterOutcome(
            0,
            "No external linter executable found. Returned static analysis only.",
        )

    def _estimate_complexity(self, tree: ast.AST) -> float:
        branches = 0
        for node in ast.walk(tree):
            if isinstance(
                node,
                (
                    ast.If,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.With,
                    ast.Try,
                    ast.BoolOp,
                    ast.ExceptHandler,
                ),
            ):
                branches += 1
        functions = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
        return float(branches + max(functions, 1))


__all__ = ["LintTool", "LintRequest", "LintResponse"]
