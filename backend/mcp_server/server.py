"""FastAPI application exposing the Ultimate MCP coding platform."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, cast

import structlog
from fastapi import Body, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastmcp import Context as MCPContext
from fastmcp import FastMCP
from pydantic import BaseModel, Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

try:
    from ..agent_integration.client import AgentDiscovery
except ImportError:  # pragma: no cover - running outside package namespace
    from agent_integration.client import AgentDiscovery
from .database.models import GraphQueryPayload, GraphUpsertPayload
from .database.neo4j_client import Neo4jClient
from .tools import (
    ExecutionRequest,
    ExecutionResponse,
    ExecutionTool,
    GenerationRequest,
    GenerationResponse,
    GenerationTool,
    GraphQueryResponse,
    GraphTool,
    GraphUpsertResponse,
    LintRequest,
    LintResponse,
    LintTool,
    TestRequest,
    TestResponse,
    TestTool,
)

# Ensure Pydantic models are fully built for runtime validation under Python 3.13.
LintRequest.model_rebuild()
LintResponse.model_rebuild()
TestRequest.model_rebuild()
TestResponse.model_rebuild()
GraphUpsertPayload.model_rebuild()
GraphUpsertResponse.model_rebuild()
GraphQueryPayload.model_rebuild()
GraphQueryResponse.model_rebuild()
ExecutionRequest.model_rebuild()
ExecutionResponse.model_rebuild()
GenerationRequest.model_rebuild()
GenerationResponse.model_rebuild()


class PromptDefinition(BaseModel):
    slug: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)


class PromptCatalog(BaseModel):
    prompts: list[PromptDefinition]


class PromptRequest(BaseModel):
    slug: str = Field(..., min_length=1, max_length=64)


class PromptResponse(BaseModel):
    prompt: PromptDefinition


PromptDefinition.model_rebuild()
PromptCatalog.model_rebuild()
PromptRequest.model_rebuild()
PromptResponse.model_rebuild()


PROMPT_DEFINITIONS: list[PromptDefinition] = [
    PromptDefinition(
        slug="proceed",
        title="Proceed (Senior Pair-Programmer)",
        body=(
            "Act as a senior pair-programmer. Proceed with the most logical next step. "
            "Internally apply multi-pass reasoning over code semantics, the dependency graph, architectural constraints, "
            "and algorithmic trade-offs. If context is missing, list the top three clarifying questions or make explicit "
            "assumptions before acting."
        ),
        tags=["reasoning", "pair-programming"],
    ),
    PromptDefinition(
        slug="evaluate",
        title="Evaluate (Comprehensive Audit)",
        body=(
            "Act as a software architect with 20+ years of experience and PhD-level computer science expertise. "
            "Perform a deep, low-level audit of the entire codebase and produce a consolidated evaluation using sequential, "
            "chain-of-thought reasoning with semantic, architectural, and graph awareness. Provide actionable step-by-step "
            "solutions with specifics, examples, prioritization, timelines, measurable success criteria, security/performance/"
            "reliability/compliance coverage, and cross-team accountability. Do not make edits—return a cohesive document "
            "mapping findings to an implementation roadmap, noting resource needs and dependency order."
        ),
        tags=["analysis", "architecture"],
    ),
    PromptDefinition(
        slug="real-a",
        title="Real-A (Production Delivery)",
        body=(
            "Act as a staff-level engineer delivering a production-ready solution—no simulations, mocks, placeholders, or MVPs."
            " Respond only with: (1) Executive summary (≤5 bullets); (2) Exact artifacts to run (paths + commands); "
            "(3) Verification steps and expected signals; (4) Results actually measured or mark UNVERIFIED with missing inputs; "
            "(5) Follow-ups if any. Fail closed if verification is impossible."
        ),
        tags=["delivery", "execution"],
    ),
    PromptDefinition(
        slug="test-a",
        title="Test-A (CI Quality Runner)",
        body=(
            "Act as a CI quality runner. Execute the full test suite with coverage and produce an automated quality report."
            " Internally reason but do not expose intermediate thoughts. Output (in order): commands/env vars to run; results summary"
            " (total passed/failed/skipped, runtime); coverage (overall % + top 10 lowest files); flakiness & slow tests (retries + 10 slowest);"
            " quality gate result; artifact locations. If execution is impossible, mark UNVERIFIED with required inputs. Never fabricate outputs."
        ),
        tags=["testing", "ci"],
    ),
    PromptDefinition(
        slug="improve",
        title="Improve (Holistic Refactor)",
        body=(
            "Act as a senior software architect. Fix, debug, refactor, enhance, and fully expand features where logical. "
            "Apply layered, sequential reasoning with semantic, architectural, relational, and graph awareness. After each change,"
            " verify behavior at micro and macro levels to maintain harmonious system operations. Do not use placeholders, TODOs, or mocks."
        ),
        tags=["refactor", "enhancement"],
    ),
    PromptDefinition(
        slug="clean",
        title="Clean (Repo Janitor)",
        body=(
            "Role: principal engineer acting as repo janitor. Goal: safely consolidate duplicates, quarantine noise in `.trash/`, refactor imports,"
            " and update docs without data loss. Follow the detailed manifest/automation/verification rules (hash scans, reference scans, manifest.json,"
            " restore.sh, guardrails, quality gate, etc.). Provide execution plan, dry-run report, scripts, codemods, documentation updates, verification,"
            " guardrails, and summary. Mark unverified steps with prerequisites; never delete—always move to `.trash/<timestamp>/`."
        ),
        tags=["cleanup", "maintenance"],
    ),
    PromptDefinition(
        slug="synthesize",
        title="Synthesize (Systems Integration)",
        body=(
            "Act as a principal project manager and senior software architect. Analyze all systems/files/code and synthesize the best elements into a cohesive,"
            " future-proof product. Ensure seamless workflow integration, robustness, and maturity."
        ),
        tags=["integration", "planning"],
    ),
]

PROMPT_INDEX: dict[str, PromptDefinition] = {prompt.slug: prompt for prompt in PROMPT_DEFINITIONS}

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.EventRenamer("message"),
        structlog.processors.JSONRenderer(
            serializer=lambda obj, **kwargs: json.dumps(obj, default=str)
        ),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

logger = structlog.get_logger("ultimate_mcp.server")


class Settings:
    """Application configuration loaded from environment variables."""

    def __init__(self) -> None:
        class _Settings(BaseSettings):
            model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

            neo4j_uri: str = Field(default="bolt://localhost:7687", validation_alias=AliasChoices("NEO4J_URI"))
            neo4j_user: str = Field(default="neo4j", validation_alias=AliasChoices("NEO4J_USER"))
            neo4j_password: str = Field(default="password123", validation_alias=AliasChoices("NEO4J_PASSWORD"))
            neo4j_database: str = Field(default="neo4j", validation_alias=AliasChoices("NEO4J_DATABASE"))
            allowed_origins: str = Field(default="http://localhost:3000", validation_alias=AliasChoices("ALLOWED_ORIGINS"))
            auth_token: str = Field(default="change-me", validation_alias=AliasChoices("AUTH_TOKEN"))
            rate_limit_rps: int = Field(default=10, validation_alias=AliasChoices("RATE_LIMIT_RPS"))
            max_request_bytes: int = Field(default=524_288, validation_alias=AliasChoices("MAX_REQUEST_BYTES"))

        data = _Settings()
        self.neo4j_uri = data.neo4j_uri
        self.neo4j_user = data.neo4j_user
        self.neo4j_password = data.neo4j_password
        self.neo4j_database = data.neo4j_database
        self.allowed_origins = [
            origin.strip()
            for origin in data.allowed_origins.split(",")
            if origin
        ]
        if data.auth_token in {"", "change-me"}:
            raise ValueError("AUTH_TOKEN must be set to a non-default value")
        if data.neo4j_password in {"", "password123"}:
            raise ValueError("NEO4J_PASSWORD must be set to a non-default value")

        self.auth_token = data.auth_token
        self.rate_limit_rps = data.rate_limit_rps
        self.max_request_bytes = data.max_request_bytes


settings = Settings()
RATE_LIMIT = f"{settings.rate_limit_rps}/second"


class ToolRegistry:
    lint: LintTool | None = None
    tests: TestTool | None = None
    graph: GraphTool | None = None
    execute: ExecutionTool | None = None
    generate: GenerationTool | None = None


registry = ToolRegistry()
neo4j_client = Neo4jClient(
    settings.neo4j_uri,
    settings.neo4j_user,
    settings.neo4j_password,
    settings.neo4j_database,
)

limiter = Limiter(key_func=get_remote_address)
http_bearer = HTTPBearer(auto_error=False)

mcp_server = FastMCP(
    name="Ultimate MCP",
    instructions=(
        "Ultimate MCP provides secure linting, testing, code execution, code generation, and graph "
        "persistence tooling backed by Neo4j."
    ),
)


@mcp_server.tool(name="lint_code", description="Run static analysis on supplied code.")
async def mcp_lint_code(payload: LintRequest, context: MCPContext) -> LintResponse:
    if registry.lint is None:
        raise RuntimeError("Lint tool not initialised")
    await context.info("Executing lint tool")
    return await registry.lint.run(payload)


@mcp_server.tool(name="run_tests", description="Execute a pytest suite in isolation.")
async def mcp_run_tests(payload: TestRequest, context: MCPContext) -> TestResponse:
    if registry.tests is None:
        raise RuntimeError("Test tool not initialised")
    await context.info("Executing run_tests tool")
    return await registry.tests.run(payload)


@mcp_server.tool(name="graph_upsert", description="Create or update graph nodes and relationships.")
async def mcp_graph_upsert(payload: GraphUpsertPayload, context: MCPContext) -> GraphUpsertResponse:
    if registry.graph is None:
        raise RuntimeError("Graph tool not initialised")
    await context.debug("Executing graph upsert")
    return await registry.graph.upsert(payload)


@mcp_server.tool(name="graph_query", description="Execute a read-only Cypher query.")
async def mcp_graph_query(payload: GraphQueryPayload, context: MCPContext) -> GraphQueryResponse:
    if registry.graph is None:
        raise RuntimeError("Graph tool not initialised")
    await context.debug("Executing graph query")
    return await registry.graph.query(payload)


@mcp_server.tool(name="execute_code", description="Run trusted Python code with sandboxing.")
async def mcp_execute_code(payload: ExecutionRequest, context: MCPContext) -> ExecutionResponse:
    if registry.execute is None:
        raise RuntimeError("Execution tool not initialised")
    await context.info("Executing code snippet")
    return await registry.execute.run(payload)


@mcp_server.tool(name="generate_code", description="Render a template into source code.")
async def mcp_generate_code(payload: GenerationRequest, context: MCPContext) -> GenerationResponse:
    if registry.generate is None:
        raise RuntimeError("Generation tool not initialised")
    await context.info("Rendering template")
    return await registry.generate.run(payload)


mcp_asgi = mcp_server.http_app(path="/mcp")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Add security headers, enforce payload limits, and attach request IDs."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.headers.get("content-length"):
            try:
                if int(request.headers["content-length"]) > settings.max_request_bytes:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        "Request body too large",
                    )
            except ValueError as error:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Invalid Content-Length header",
                ) from error

        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        request.state.request_id = request_id
        logger.info(
            "request.start",
            method=request.method,
            path=request.url.path,
            request_id=request_id,
            client=str(request.client),
        )
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        logger.info(
            "request.end",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            request_id=request_id,
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await neo4j_client.connect()
    registry.lint = LintTool(neo4j_client)
    registry.tests = TestTool(neo4j_client)
    registry.graph = GraphTool(neo4j_client)
    registry.execute = ExecutionTool(neo4j_client)
    registry.generate = GenerationTool(neo4j_client)
    app.state.settings = settings
    app.state.neo4j = neo4j_client
    app.state.tools = registry
    app.state.agent_discovery = AgentDiscovery(base_url="http://localhost:8000")

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mcp_asgi.lifespan(app))
        yield

    await neo4j_client.close()


def rate_limit_handler(request: Request, exc: Exception) -> Response:
    if isinstance(exc, RateLimitExceeded):
        detail = "Rate limit exceeded"
    else:
        detail = "Unexpected error"
    body = json.dumps({"detail": detail})
    return Response(content=body, status_code=429, media_type="application/json")

app = FastAPI(title="Ultimate MCP Platform", lifespan=lifespan)

app.add_middleware(RequestContextMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    allow_credentials=False,
)
app.add_middleware(SlowAPIMiddleware)

app.mount("/mcp", mcp_asgi)


def _require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer)) -> None:
    if settings.auth_token is None:
        return
    if credentials is None or credentials.credentials != settings.auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _get_lint_tool(request: Request) -> LintTool:
    tools = cast(ToolRegistry, request.app.state.tools)
    tool = tools.lint
    if tool is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Lint tool not available")
    return tool


def _get_test_tool(request: Request) -> TestTool:
    tools = cast(ToolRegistry, request.app.state.tools)
    tool = tools.tests
    if tool is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Test tool not available")
    return tool


def _get_graph_tool(request: Request) -> GraphTool:
    tools = cast(ToolRegistry, request.app.state.tools)
    tool = tools.graph
    if tool is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Graph tool not available")
    return tool


def _get_exec_tool(request: Request) -> ExecutionTool:
    tools = cast(ToolRegistry, request.app.state.tools)
    tool = tools.execute
    if tool is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Execution tool not available")
    return tool


def _get_gen_tool(request: Request) -> GenerationTool:
    tools = cast(ToolRegistry, request.app.state.tools)
    tool = tools.generate
    if tool is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Generation tool not available")
    return tool


router = APIRouter()


@router.get("/health")
async def health() -> dict[str, Any]:
    return {
        "service": "ok",
        "neo4j": await neo4j_client.health_check(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics")
async def metrics() -> dict[str, Any]:
    metrics = await neo4j_client.get_metrics()
    return metrics.model_dump()


@router.get("/prompts", response_model=list[PromptDefinition])
async def list_prompts_route() -> list[PromptDefinition]:
    return PROMPT_DEFINITIONS


@router.get("/prompts/{slug}", response_model=PromptDefinition)
async def get_prompt_route(slug: str) -> PromptDefinition:
    prompt = PROMPT_INDEX.get(slug) or PROMPT_INDEX.get(slug.lower())
    if prompt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt not found")
    return prompt


@router.post("/lint_code")
@limiter.limit(RATE_LIMIT)
async def lint_code(
    request: Request,
    tool: LintTool = Depends(_get_lint_tool),
) -> JSONResponse:
    payload = LintRequest.model_validate(await request.json())
    result = await tool.run(payload)
    return JSONResponse(result.model_dump())


@router.post("/run_tests")
@limiter.limit(RATE_LIMIT)
async def run_tests(
    request: Request,
    tool: TestTool = Depends(_get_test_tool),
    __: None = Depends(_require_auth),
) -> JSONResponse:
    payload = TestRequest.model_validate(await request.json())
    result = await tool.run(payload)
    return JSONResponse(result.model_dump())


@router.post("/graph_upsert")
@limiter.limit(RATE_LIMIT)
async def graph_upsert(
    request: Request,
    tool: GraphTool = Depends(_get_graph_tool),
    __: None = Depends(_require_auth),
) -> JSONResponse:
    payload = GraphUpsertPayload.model_validate(await request.json())
    result = await tool.upsert(payload)
    return JSONResponse(result.model_dump())


@router.post("/graph_query")
@limiter.limit(RATE_LIMIT)
async def graph_query(
    request: Request,
    tool: GraphTool = Depends(_get_graph_tool),
) -> JSONResponse:
    payload = GraphQueryPayload.model_validate(await request.json())
    result = await tool.query(payload)
    return JSONResponse(result.model_dump())


@router.post("/execute_code")
@limiter.limit(RATE_LIMIT)
async def execute_code(
    request: Request,
    tool: ExecutionTool = Depends(_get_exec_tool),
    __: None = Depends(_require_auth),
) -> JSONResponse:
    payload = ExecutionRequest.model_validate(await request.json())
    result = await tool.run(payload)
    return JSONResponse(result.model_dump())


@router.post("/generate_code")
@limiter.limit(RATE_LIMIT)
async def generate_code(
    request: Request,
    tool: GenerationTool = Depends(_get_gen_tool),
    __: None = Depends(_require_auth),
) -> JSONResponse:
    payload = GenerationRequest.model_validate(await request.json())
    result = await tool.run(payload)
    return JSONResponse(result.model_dump())


@mcp_server.tool(name="list_prompts", description="List the built-in system prompts.")
async def mcp_list_prompts(context: MCPContext) -> PromptCatalog:
    await context.info("Returning prompt catalog", extra={"count": len(PROMPT_DEFINITIONS)})
    return PromptCatalog(prompts=PROMPT_DEFINITIONS)


@mcp_server.tool(name="get_prompt", description="Retrieve a built-in system prompt by slug.")
async def mcp_get_prompt(payload: PromptRequest, context: MCPContext) -> PromptResponse:
    slug = payload.slug.lower()
    prompt = PROMPT_INDEX.get(slug)
    if prompt is None:
        raise ValueError(f"Unknown prompt slug: {payload.slug}")
    await context.info("Returning prompt", extra={"slug": slug})
    return PromptResponse(prompt=prompt)


app.include_router(router)


__all__ = ["app", "settings"]
