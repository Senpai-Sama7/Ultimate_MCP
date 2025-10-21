"""JavaScript execution tool with Node.js runtime."""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .exec_tool import ExecutionRequest, ExecutionResponse, ExecutionResult


class JavaScriptExecutionTool:
    """JavaScript code execution with Node.js runtime."""
    
    def __init__(self, max_concurrent: int = 3, node_timeout: int = 30):
        self.max_concurrent = max_concurrent
        self.node_timeout = node_timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run(self, request: ExecutionRequest) -> ExecutionResponse:
        """Execute JavaScript code using Node.js."""
        if request.language.lower() not in ["javascript", "js", "node"]:
            raise ValueError(f"Unsupported language: {request.language}")
        
        async with self._semaphore:
            result = await self._execute_javascript_async(request)
            
            return ExecutionResponse(
                id=result.id,
                language="javascript",
                return_code=result.return_code,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=result.duration_seconds,
            )
    
    async def _execute_javascript_async(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute JavaScript code using Node.js subprocess."""
        with TemporaryDirectory(prefix="ultimate_mcp_js_") as tmp:
            # Create package.json for isolated environment
            package_json = {
                "name": "mcp-execution",
                "version": "1.0.0",
                "type": "module",
                "dependencies": {}
            }
            
            package_path = Path(tmp) / "package.json"
            package_path.write_text(json.dumps(package_json, indent=2))
            
            # Write the JavaScript code
            script_path = Path(tmp) / "script.js"
            
            # Wrap user code with safety measures
            wrapped_code = self._wrap_javascript_code(request.code)
            script_path.write_text(wrapped_code, encoding="utf-8")
            
            start = time.perf_counter()
            
            try:
                # Check if Node.js is available
                node_check = await asyncio.create_subprocess_exec(
                    "node", "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await node_check.communicate()
                
                if node_check.returncode != 0:
                    return ExecutionResult(
                        id=str(uuid.uuid4()),
                        language="javascript",
                        return_code=1,
                        stdout="",
                        stderr="Node.js not available on system",
                        duration_seconds=0.0,
                    )
                
                # Execute JavaScript with Node.js
                process = await asyncio.create_subprocess_exec(
                    "node", str(script_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmp,
                    env={
                        "NODE_ENV": "sandbox",
                        "NODE_OPTIONS": "--max-old-space-size=128",  # Limit memory
                    }
                )
                
                # Wait for completion with timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=min(request.timeout_seconds, self.node_timeout)
                )
                
                duration = time.perf_counter() - start
                
                return ExecutionResult(
                    id=str(uuid.uuid4()),
                    language="javascript",
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
                    language="javascript",
                    return_code=-1,
                    stdout="",
                    stderr=f"Execution timed out after {request.timeout_seconds} seconds",
                    duration_seconds=duration,
                )
            
            except Exception as e:
                duration = time.perf_counter() - start
                return ExecutionResult(
                    id=str(uuid.uuid4()),
                    language="javascript",
                    return_code=1,
                    stdout="",
                    stderr=f"Execution error: {e}",
                    duration_seconds=duration,
                )
    
    def _wrap_javascript_code(self, user_code: str) -> str:
        """Wrap user code with safety measures and timeout."""
        return f"""
// Security and safety wrapper for user code
(async function() {{
    // Disable dangerous globals
    if (typeof global !== 'undefined') {{
        delete global.process;
        delete global.require;
    }}
    
    // Set execution timeout
    const timeoutId = setTimeout(() => {{
        console.error('Script execution timed out');
        process.exit(124);
    }}, 25000); // 25 second internal timeout
    
    try {{
        // User code execution
        {user_code}
        
        // Clear timeout if execution completes
        clearTimeout(timeoutId);
    }} catch (error) {{
        clearTimeout(timeoutId);
        console.error('Runtime error:', error.message);
        process.exit(1);
    }}
}})().catch(error => {{
    console.error('Async error:', error.message);
    process.exit(1);
}});
"""


class MultiLanguageExecutionTool:
    """Multi-language execution tool supporting Python and JavaScript."""
    
    def __init__(self):
        self.python_tool = None  # Will be injected
        self.js_tool = JavaScriptExecutionTool()
    
    async def run(self, request: ExecutionRequest) -> ExecutionResponse:
        """Route execution to appropriate language tool."""
        language = request.language.lower()
        
        if language == "python":
            if not self.python_tool:
                from .async_exec_tool import AsyncExecutionTool
                self.python_tool = AsyncExecutionTool()
            return await self.python_tool.run(request)
        
        elif language in ["javascript", "js", "node"]:
            return await self.js_tool.run(request)
        
        else:
            raise ValueError(f"Unsupported language: {request.language}")


__all__ = ["JavaScriptExecutionTool", "MultiLanguageExecutionTool"]
