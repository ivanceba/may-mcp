"""Every advertised tool publishes explicit, behavior-accurate MCP safety hints."""

import pytest


@pytest.mark.parametrize("writes,count", [(False, 14), (True, 29)])
async def test_all_tools_publish_four_explicit_boolean_hints(
    server_factory, mcp_client_factory, writes, count
):
    requests = []
    server = server_factory(lambda request: requests.append(request), writes=writes)
    async with mcp_client_factory(server) as client:
        catalogue = (await client.list_tools()).model_dump(by_alias=True, exclude_none=True)

    assert len(catalogue["tools"]) == count
    for tool in catalogue["tools"]:
        name = tool["name"]
        create = name.startswith("may_create_")
        change = name.startswith(("may_update_", "may_delete_"))
        expected = {
            "readOnlyHint": not (create or change),
            "destructiveHint": change,
            "idempotentHint": not create,
            "openWorldHint": True,
        }
        annotations = tool.get("annotations", {})
        for hint, value in expected.items():
            assert type(annotations.get(hint)) is bool, (name, hint, annotations)
            assert annotations[hint] is value, (name, hint, annotations)
    assert requests == []
