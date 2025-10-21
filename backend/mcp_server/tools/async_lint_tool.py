"""Async lint tool with non-blocking subprocess calls."""

from __future__ import annotations

import ast
import asyncio
import hashlib
import sys
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .lint_tool import LintRequest, LintResponse
from ..database.neo4j_client import Neo4jClient


class AsyncLintTool:
    """Async code linting tool with non-blocking subprocess calls."""
    
    def __init__(self, neo4j_client: Neo4jClient, max_concurrent: int = 3):
        self.neo4j_client = neo4j_client
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run(self, request: LintRequest) -> LintResponse:
        """Run linting asynchronously without blocking the event loop."""
        async with self._semaphore:
            # Parse AST (fast, synchronous)
            try:
                tree = ast.parse(request.code)
            except SyntaxError as e:
                return LintResponse(
                    id=str(uuid.uuid4()),
                    code_hash=hashlib.sha256(request.code.encode()).hexdigest(),
                    functions=[],
                    classes=[],
                    imports=[],
                    complexity=0.0,
                    linter_exit_code=1,
                    linter_output=f"Syntax error: {e}",
                )
            
            # Extract metadata
            functions = sorted({
                node.name for node in ast.walk(tree) 
                if isinstance(node, ast.FunctionDef)
            })
            classes = sorted({
                node.name for node in ast.walk(tree) 
                if isinstance(node, ast.ClassDef)
            })
            imports = sorted({
                node.name for node in ast.walk(tree) 
                if isinstance(node, ast.Import)
            })
            
            # Calculate complexity (simplified)
            complexity = len([
                node for node in ast.walk(tree) 
                if isinstance(node, (ast.If, ast.For, ast.While, ast.Try))
            ])
            
            # Run external linter asynchronously
            linter_exit_code, linter_output = await self._run_external_linter_async(
                request.code, request.language
            )
            
            code_hash = hashlib.sha256(request.code.encode()).hexdigest()
            
            response = LintResponse(
                id=str(uuid.uuid4()),
                code_hash=code_hash,
                functions=functions,
                classes=classes,
                imports=imports,
                complexity=float(complexity),
                linter_exit_code=linter_exit_code,
                linter_output=linter_output,
            )
            
            # Persist to database asynchronously
            await self._persist_async(response)
            
            return response
    
    async def _run_external_linter_async(self, code: str, language: str) -> tuple[int, str]:
        """Run external linter using async subprocess."""
        if language.lower() != "python":
            return 0, "Linting not supported for this language"
        
        with TemporaryDirectory(prefix="ultimate_mcp_lint_") as tmp:
            script_path = Path(tmp) / "code.py"
            script_path.write_text(code, encoding="utf-8")
            
            # Run flake8 (lightweight, fast)
            try:
                process = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "flake8", 
                    "--max-line-length=100",
                    "--ignore=E203,W503",
                    str(script_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmp,
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=10.0  # 10 second timeout for linting
                )
                
                output = (stdout or b"").decode("utf-8") + (stderr or b"").decode("utf-8")
                return process.returncode or 0, output.strip()
                
            except asyncio.TimeoutError:
                return 1, "Linting timed out"
            except Exception as e:
                return 1, f"Linting failed: {e}"
    
    async def _persist_async(self, response: LintResponse) -> None:
        """Persist lint result to Neo4j asynchronously."""
        query = """
        MERGE (l:LintResult {id: $id})
        SET l += {
            code_hash: $code_hash,
            functions: $functions,
            classes: $classes,
            imports: $imports,
            complexity: $complexity,
            linter_exit_code: $linter_exit_code,
            linter_output: $linter_output,
            timestamp: datetime()
        }
        """
        
        await self.neo4j_client.execute_write(query, {
            "id": response.id,
            "code_hash": response.code_hash,
            "functions": response.functions,
            "classes": response.classes,
            "imports": response.imports,
            "complexity": response.complexity,
            "linter_exit_code": response.linter_exit_code,
            "linter_output": response.linter_output,
        })


__all__ = ["AsyncLintTool"]
