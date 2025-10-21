from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_fastmcp_resource_registration(server_module):
    resources = await server_module.mcp_server._resource_manager.list_resources()
    resource_map = {str(resource.uri): resource for resource in resources}

    assert set(resource_map) >= {
        definition.uri for definition in server_module.RESOURCE_DEFINITIONS
    }

    for definition in server_module.RESOURCE_DEFINITIONS:
        resource = resource_map[definition.uri]
        content = await resource.read()
        expected = definition.path.read_text(encoding="utf-8")
        assert content == expected
