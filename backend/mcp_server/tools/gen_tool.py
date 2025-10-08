"""Code generation tool using templating."""

from __future__ import annotations

import uuid

from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel, Field

from ..database.models import GeneratedCode
from ..database.neo4j_client import Neo4jClient
from ..utils.validation import ensure_supported_language

_env = Environment(
    autoescape=False,  # noqa: S701 - generating code templates deliberately disables autoescape.
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


class GenerationRequest(BaseModel):
    template: str = Field(..., description="Jinja2 template to render.")
    context: dict[str, object] = Field(default_factory=dict, description="Template variables.")
    language: str = Field(default="python")


class GenerationResponse(BaseModel):
    id: str
    language: str
    output: str


class GenerationTool:
    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    async def run(self, request: GenerationRequest) -> GenerationResponse:
        ensure_supported_language(request.language)
        template = _env.from_string(request.template)
        output = template.render(**request.context)
        result = GeneratedCode(
            id=str(uuid.uuid4()),
            language=request.language,
            template_used=request.template,
            context_keys=sorted(request.context.keys()),
            output=output,
        )
        await self._persist(result)
        return GenerationResponse(id=result.id, language=result.language, output=result.output)

    async def _persist(self, result: GeneratedCode) -> None:
        await self._neo4j.execute_write(
            """
            MERGE (r:GeneratedCode {id: $id})
            SET r += {
                language: $language,
                template_used: $template_used,
                context_keys: $context_keys,
                output: $output,
                created_at: datetime($created_at)
            }
            """,
            {
                "id": result.id,
                "language": result.language,
                "template_used": result.template_used,
                "context_keys": result.context_keys,
                "output": result.output,
                "created_at": result.created_at.isoformat(),
            },
        )


__all__ = ["GenerationTool", "GenerationRequest", "GenerationResponse"]
