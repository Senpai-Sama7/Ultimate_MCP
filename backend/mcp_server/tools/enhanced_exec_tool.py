"""Enhanced secure code execution tool with advanced features."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging

# The resource module is POSIX-only; guard imports so Windows agents degrade gracefully.
try:
    import resource  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - Windows environments
    resource = None  # type: ignore[assignment]
import sys
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, AsyncGenerator

from pydantic import BaseModel, Field

from ..database.neo4j_client_enhanced import EnhancedNeo4jClient
from ..utils.enhanced_security import SecurityContext, SecurityLevel, ensure_safe_python

logger = logging.getLogger(__name__)


@dataclass
class ExecutionLimits:
    """Resource limits for code execution."""
    max_memory_mb: int = 128
    max_cpu_time_seconds: int = 30
    max_file_size_mb: int = 10
    max_processes: int = 1
    max_open_files: int = 64


@dataclass
class ExecutionMetrics:
    """Execution performance metrics."""
    cpu_time: float
    memory_peak_mb: float
    io_operations: int
    network_calls: int = 0


class ExecutionRequest(BaseModel):
    """Enhanced execution request with security context."""
    code: str = Field(..., description="Code snippet to execute")
    language: str = Field(default="python", description="Programming language")
    timeout_seconds: float = Field(default=8.0, ge=0.5, le=60.0)
    limits: dict[str, Any] = Field(default_factory=dict, description="Resource limits")
    environment: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    cache_enabled: bool = Field(default=True, description="Enable result caching")
    debug_mode: bool = Field(default=False, description="Enable debug output")


class ExecutionResponse(BaseModel):
    """Enhanced execution response with metrics."""
    id: str
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    metrics: dict[str, Any] = Field(default_factory=dict)
    cached: bool = False
    security_warnings: list[str] = Field(default_factory=list)


class ExecutionCache:
    """In-memory cache for execution results."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: dict[str, tuple[ExecutionResponse, float]] = {}
    
    def _generate_key(self, request: ExecutionRequest) -> str:
        """Generate cache key from request."""
        content = f"{request.code}:{request.language}:{request.timeout_seconds}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get(self, request: ExecutionRequest) -> ExecutionResponse | None:
        """Get cached result if available and valid."""
        if not request.cache_enabled:
            return None
            
        key = self._generate_key(request)
        if key in self.cache:
            result, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                result.cached = True
                return result
            else:
                del self.cache[key]
        return None
    
    def set(self, request: ExecutionRequest, response: ExecutionResponse) -> None:
        """Cache execution result."""
        if not request.cache_enabled or response.return_code != 0:
            return
            
        key = self._generate_key(request)
        
        # Evict oldest entries if cache is full
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        
        self.cache[key] = (response, time.time())


class EnhancedExecutionTool:
    """Enhanced execution tool with advanced security and monitoring."""
    
    def __init__(self, neo4j: EnhancedNeo4jClient):
        self.neo4j = neo4j
        self.cache = ExecutionCache()
        self.supported_languages = {"python", "javascript", "bash"}
        
    @staticmethod
    def _snapshot_usage():
        if resource is None:
            return None
        try:
            return resource.getrusage(resource.RUSAGE_CHILDREN)
        except Exception:  # pragma: no cover - platform-specific failure
            return None

    @staticmethod
    def _compute_usage_metrics(start_usage, language: str) -> dict[str, Any]:
        metrics: dict[str, Any] = {"language": language}
        if resource is None or start_usage is None:
            return metrics
        try:
            end_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        except Exception:  # pragma: no cover - platform-specific failure
            return metrics

        def _delta(attr: str) -> float:
            return getattr(end_usage, attr, 0.0) - getattr(start_usage, attr, 0.0)

        cpu_time = max(0.0, _delta("ru_utime") + _delta("ru_stime"))
        io_ops = max(0, int(_delta("ru_inblock") + _delta("ru_oublock")))
        peak_raw = max(0.0, end_usage.ru_maxrss - start_usage.ru_maxrss)
        if sys.platform == "darwin":
            memory_peak_mb = peak_raw / (1024 * 1024)
        else:
            memory_peak_mb = peak_raw / 1024

        metrics.update(
            {
                "cpu_time": cpu_time,
                "memory_peak_mb": round(memory_peak_mb, 3),
                "io_operations": io_ops,
            }
        )
        return metrics

    async def run(
        self, 
        request: ExecutionRequest, 
        security_context: SecurityContext | None = None
    ) -> ExecutionResponse:
        """Execute code with enhanced security and monitoring."""
        
        # Check cache first
        cached_result = self.cache.get(request)
        if cached_result:
            logger.info(f"Returning cached result for execution {cached_result.id}")
            return cached_result
        
        # Validate security context
        if security_context and security_context.security_level == SecurityLevel.PUBLIC:
            if request.language != "python" or len(request.code) > 1000:
                raise PermissionError("Public access limited to Python code under 1000 characters")
        
        # Validate language support
        if request.language not in self.supported_languages:
            raise ValueError(f"Unsupported language: {request.language}")
        
        # Enhanced security validation
        security_warnings = []
        if resource is None:
            security_warnings.append(
                "POSIX resource module unavailable; OS-level execution limits not enforced"
            )
        if request.language == "python":
            try:
                ensure_safe_python(request.code, max_complexity=200)
            except Exception as e:
                security_warnings.append(str(e))
                if security_context and security_context.security_level == SecurityLevel.PUBLIC:
                    raise
        
        # Execute with appropriate handler
        if request.language == "python":
            result = await self._execute_python(request, security_warnings)
        elif request.language == "javascript":
            result = await self._execute_javascript(request, security_warnings)
        elif request.language == "bash":
            result = await self._execute_bash(request, security_warnings)
        else:
            raise ValueError(f"Execution handler not implemented for {request.language}")
        
        # Cache successful results
        self.cache.set(request, result)
        
        # Persist to database
        await self._persist_result(result, security_context)
        
        return result
    
    async def _execute_python(
        self, 
        request: ExecutionRequest, 
        security_warnings: list[str]
    ) -> ExecutionResponse:
        """Execute Python code with resource limits."""
        
        limits = ExecutionLimits(**request.limits)
        
        async with self._create_sandbox() as sandbox_path:
            script_path = sandbox_path / "script.py"
            script_path.write_text(request.code, encoding="utf-8")
            
            # Prepare execution environment
            env = {
                "PYTHONPATH": "",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
                **request.environment
            }
            
            def _preexec() -> None:
                """Apply resource limits inside the child process before user code runs."""
                if resource is None:
                    return
                # Memory limit
                try:
                    resource.setrlimit(
                        resource.RLIMIT_AS, (limits.max_memory_mb * 1024 * 1024, limits.max_memory_mb * 1024 * 1024)
                    )
                except (ValueError, OSError):  # pragma: no cover - limit not supported
                    pass
                # CPU time
                try:
                    resource.setrlimit(resource.RLIMIT_CPU, (limits.max_cpu_time_seconds, limits.max_cpu_time_seconds))
                except (ValueError, OSError):  # pragma: no cover
                    pass
                # Process and file descriptor ceilings
                for limit_name, value in (
                    ("RLIMIT_NPROC", limits.max_processes),
                    ("RLIMIT_NOFILE", limits.max_open_files),
                ):
                    rlimit = getattr(resource, limit_name, None)
                    if rlimit is None:
                        continue
                    try:
                        resource.setrlimit(rlimit, (value, value))
                    except (ValueError, OSError):  # pragma: no cover
                        continue
                # Limit file sizes written during execution
                rlimit_fsize = getattr(resource, "RLIMIT_FSIZE", None)
                if rlimit_fsize is not None:
                    max_bytes = limits.max_file_size_mb * 1024 * 1024
                    try:
                        resource.setrlimit(rlimit_fsize, (max_bytes, max_bytes))
                    except (ValueError, OSError):  # pragma: no cover
                        pass

            cmd = [
                sys.executable,
                "-I",  # Isolated mode: ignore PYTHONPATH/user site-packages
                "-B",  # Disable .pyc generation inside the sandbox
                str(script_path),
            ]
            
            start_time = time.perf_counter()
            start_rusage = self._snapshot_usage()
            
            try:
                kwargs: dict[str, Any] = {
                    "stdout": asyncio.subprocess.PIPE,
                    "stderr": asyncio.subprocess.PIPE,
                    "cwd": sandbox_path,
                    "env": env,
                }
                if resource is not None:
                    kwargs["preexec_fn"] = _preexec  # type: ignore[assignment]

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    **kwargs,
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=request.timeout_seconds
                )
                
                return_code = process.returncode
                
            except asyncio.TimeoutError:
                if process:
                    process.kill()
                    await process.wait()
                return_code = -1
                stdout = b""
                stderr = b"Execution timed out"
            
            except Exception as e:
                return_code = -1
                stdout = b""
                stderr = str(e).encode()
            
            duration = time.perf_counter() - start_time
            metrics = self._compute_usage_metrics(start_rusage, request.language)
            metrics["duration_seconds"] = duration
            metrics["limits_applied"] = limits.__dict__
            metrics.setdefault("cpu_time", duration)
            
            return ExecutionResponse(
                id=str(uuid.uuid4()),
                return_code=return_code,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                duration_seconds=duration,
                metrics=metrics,
                security_warnings=security_warnings,
            )
    
    async def _execute_javascript(
        self, 
        request: ExecutionRequest, 
        security_warnings: list[str]
    ) -> ExecutionResponse:
        """Execute JavaScript code using Node.js."""
        
        async with self._create_sandbox() as sandbox_path:
            script_path = sandbox_path / "script.js"
            script_path.write_text(request.code, encoding="utf-8")
            
            cmd = ["node", "--max-old-space-size=128", str(script_path)]
            
            start_time = time.perf_counter()
            start_rusage = self._snapshot_usage()
            
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=sandbox_path,
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=request.timeout_seconds
                )
                
                return_code = process.returncode
                
            except asyncio.TimeoutError:
                if process:
                    process.kill()
                    await process.wait()
                return_code = -1
                stdout = b""
                stderr = b"Execution timed out"
            
            except Exception as e:
                return_code = -1
                stdout = b""
                stderr = str(e).encode()
            
            duration = time.perf_counter() - start_time
            metrics = self._compute_usage_metrics(start_rusage, "javascript")
            metrics["duration_seconds"] = duration
            metrics.setdefault("cpu_time", duration)

            return ExecutionResponse(
                id=str(uuid.uuid4()),
                return_code=return_code,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                duration_seconds=duration,
                metrics=metrics,
                security_warnings=security_warnings,
            )
    
    async def _execute_bash(
        self, 
        request: ExecutionRequest, 
        security_warnings: list[str]
    ) -> ExecutionResponse:
        """Execute Bash script with restrictions."""
        
        # Additional security for bash
        if any(dangerous in request.code for dangerous in ["rm -rf", "sudo", "curl", "wget"]):
            security_warnings.append("Potentially dangerous bash commands detected")
        
        async with self._create_sandbox() as sandbox_path:
            script_path = sandbox_path / "script.sh"
            script_path.write_text(request.code, encoding="utf-8")
            script_path.chmod(0o755)
            
            cmd = ["bash", str(script_path)]
            
            start_time = time.perf_counter()
            start_rusage = self._snapshot_usage()
            
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=sandbox_path,
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=request.timeout_seconds
                )
                
                return_code = process.returncode
                
            except asyncio.TimeoutError:
                if process:
                    process.kill()
                    await process.wait()
                return_code = -1
                stdout = b""
                stderr = b"Execution timed out"
            
            except Exception as e:
                return_code = -1
                stdout = b""
                stderr = str(e).encode()
            
            duration = time.perf_counter() - start_time
            metrics = self._compute_usage_metrics(start_rusage, "bash")
            metrics["duration_seconds"] = duration
            metrics.setdefault("cpu_time", duration)

            return ExecutionResponse(
                id=str(uuid.uuid4()),
                return_code=return_code,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                duration_seconds=duration,
                metrics=metrics,
                security_warnings=security_warnings,
            )
    
    @asynccontextmanager
    async def _create_sandbox(self) -> AsyncGenerator[Path, None]:
        """Create secure execution sandbox."""
        with TemporaryDirectory(prefix="enhanced_mcp_exec_") as tmp_dir:
            sandbox_path = Path(tmp_dir)
            
            # Set restrictive permissions
            sandbox_path.chmod(0o700)
            
            yield sandbox_path
    
    async def _persist_result(
        self, 
        result: ExecutionResponse, 
        security_context: SecurityContext | None
    ) -> None:
        """Persist execution result with enhanced metadata."""
        
        await self.neo4j.execute_write_with_retry(
            """
            MERGE (r:ExecutionResult {id: $id})
            SET r += {
                return_code: $return_code,
                stdout: $stdout,
                stderr: $stderr,
                duration_seconds: $duration_seconds,
                metrics: $metrics,
                security_warnings: $security_warnings,
                cached: $cached,
                user_id: $user_id,
                security_level: $security_level,
                created_at: datetime($created_at)
            }
            """,
            {
                "id": result.id,
                "return_code": result.return_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_seconds": result.duration_seconds,
                "metrics": json.dumps(result.metrics),
                "security_warnings": result.security_warnings,
                "cached": result.cached,
                "user_id": security_context.user_id if security_context else None,
                "security_level": security_context.security_level.value if security_context else "public",
                "created_at": time.time(),
            },
        )
    
    async def get_execution_stats(self) -> dict[str, Any]:
        """Get execution statistics."""
        
        stats = await self.neo4j.execute_read_with_retry(
            """
            MATCH (r:ExecutionResult)
            RETURN 
                count(r) as total_executions,
                avg(r.duration_seconds) as avg_duration,
                sum(CASE WHEN r.return_code = 0 THEN 1 ELSE 0 END) as successful_executions,
                sum(CASE WHEN r.cached THEN 1 ELSE 0 END) as cached_executions
            """
        )
        
        if stats:
            return {
                "total_executions": stats[0]["total_executions"],
                "average_duration": stats[0]["avg_duration"],
                "success_rate": stats[0]["successful_executions"] / stats[0]["total_executions"] if stats[0]["total_executions"] > 0 else 0,
                "cache_hit_rate": stats[0]["cached_executions"] / stats[0]["total_executions"] if stats[0]["total_executions"] > 0 else 0,
                "cache_size": len(self.cache.cache),
            }
        
        return {"total_executions": 0, "cache_size": len(self.cache.cache)}


__all__ = ["EnhancedExecutionTool", "ExecutionRequest", "ExecutionResponse", "ExecutionLimits"]
