import os
import sys
import json
import random
import importlib.util
import pytest
from mcp.types import ListToolsRequest
from tests.utils.test_tools import get_test_id, run_tool_test


def _load_server_module():
    server_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "src",
        "servers",
        "livekit",
        "main.py",
    )
    server_path = os.path.abspath(server_path)
    spec = importlib.util.spec_from_file_location("livekit_server", server_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["livekit_server"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def server_and_module():
    mod = _load_server_module()
    server = mod.create_server("test-user")
    return server, mod


@pytest.fixture(autouse=True)
def clear_env_creds():
    saved = {
        k: os.environ.pop(k, None)
        for k in ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]
    }
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v


@pytest.fixture
def set_env_creds():
    os.environ["LIVEKIT_URL"] = "http://localhost:7880"
    os.environ["LIVEKIT_API_KEY"] = "test-key"
    os.environ["LIVEKIT_API_SECRET"] = "test-secret"
    yield
    for k in ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]:
        os.environ.pop(k, None)


TOOL_TESTS = [
    {
        "name": "create_room",
        "args_template": 'with name="pfmcp-test-room-{random_id}"',
        "expected_keywords": ["name", "sid"],
        "description": "create a new LiveKit room and return its name and sid",
        "setup": lambda context: {"random_id": str(random.randint(10000, 99999))},
        "skip": True,
    },
    {
        "name": "delete_room",
        "args_template": 'with room="pfmcp-test-room-{random_id}"',
        "expected_keywords": ["status"],
        "description": "delete a LiveKit room and return a success status",
        "depends_on": ["random_id"],
        "skip": True,
    },
    {
        "name": "list_rooms",
        "args_template": "",
        "expected_keywords": ["rooms"],
        "description": "list all LiveKit rooms and return the rooms list",
        "skip": True,
    },
    {
        "name": "generate_join_token",
        "args_template": 'with room="test-room" identity="test-user-{random_id}"',
        "expected_keywords": ["token", "url"],
        "description": "generate a join token for a LiveKit room and return the token and url",
        "setup": lambda context: {"random_id": str(random.randint(10000, 99999))},
        "skip": True,
    },
    {
        "name": "list_participants",
        "args_template": 'with room="test-room"',
        "expected_keywords": ["participants"],
        "description": "list participants in a LiveKit room",
        "skip": True,
    },
    {
        "name": "get_participant",
        "args_template": 'with room="test-room" identity="test-user-{random_id}"',
        "expected_keywords": ["identity"],
        "description": "get details about a specific participant in a LiveKit room",
        "setup": lambda context: {"random_id": str(random.randint(10000, 99999))},
        "skip": True,
    },
    {
        "name": "update_participant",
        "args_template": 'with room="test-room" identity="test-user-{random_id}" metadata=\'{"role": "moderator"}\'',
        "expected_keywords": ["identity"],
        "description": "update participant metadata in a LiveKit room",
        "setup": lambda context: {"random_id": str(random.randint(10000, 99999))},
        "skip": True,
    },
    {
        "name": "remove_participant",
        "args_template": 'with room="test-room" identity="test-user-{random_id}"',
        "expected_keywords": ["status"],
        "description": "remove a participant from a LiveKit room",
        "setup": lambda context: {"random_id": str(random.randint(10000, 99999))},
        "skip": True,
    },
    {
        "name": "mute_participant_track",
        "args_template": 'with room="test-room" identity="test-user-{random_id}" track_sid="TR_test" muted=true',
        "expected_keywords": ["track_sid"],
        "description": "mute a participant's track in a LiveKit room",
        "setup": lambda context: {"random_id": str(random.randint(10000, 99999))},
        "skip": True,
    },
    {
        "name": "update_room_metadata",
        "args_template": 'with room="test-room" metadata=\'{"key": "value"}\'',
        "expected_keywords": ["room"],
        "description": "update metadata for a LiveKit room",
        "skip": True,
    },
]

SHARED_CONTEXT = {}


@pytest.fixture(scope="module")
def context():
    return SHARED_CONTEXT


class TestToolDefinitions:
    @pytest.mark.asyncio
    async def test_list_tools_returns_all_phase1_tools(self, server_and_module):
        server, _ = server_and_module
        handler = server.request_handlers[ListToolsRequest]
        result = await handler(None)
        tools = result.root.tools
        tool_names = [t.name for t in tools]

        expected_tools = [
            "create_room",
            "delete_room",
            "list_rooms",
            "generate_join_token",
            "list_participants",
            "get_participant",
            "update_participant",
            "remove_participant",
            "mute_participant_track",
            "update_room_metadata",
        ]
        for name in expected_tools:
            assert name in tool_names, f"Missing tool: {name}"
        assert len(tools) == len(expected_tools), (
            f"Expected {len(expected_tools)} tools, got {len(tools)}. "
            f"Extra tools: {set(tool_names) - set(expected_tools)}"
        )

    @pytest.mark.asyncio
    async def test_tool_schemas_have_required_fields(self, server_and_module):
        server, _ = server_and_module
        handler = server.request_handlers[ListToolsRequest]
        result = await handler(None)
        tools = result.root.tools

        required_fields = {
            "create_room": {"name"},
            "delete_room": {"room"},
            "list_participants": {"room"},
            "get_participant": {"room", "identity"},
            "update_participant": {"room", "identity"},
            "remove_participant": {"room", "identity"},
            "mute_participant_track": {"room", "identity", "track_sid", "muted"},
            "update_room_metadata": {"room", "metadata"},
            "generate_join_token": {"room", "identity"},
        }

        for tool in tools:
            if tool.name in required_fields:
                props = tool.inputSchema.get("properties", {})
                required = tool.inputSchema.get("required", [])
                for field in required_fields[tool.name]:
                    assert (
                        field in props
                    ), f"Tool '{tool.name}' missing field '{field}' in properties"
                    assert (
                        field in required
                    ), f"Tool '{tool.name}' missing field '{field}' in required list"

    def test_get_initialization_options(self, server_and_module):
        server, mod = server_and_module
        opts = mod.get_initialization_options(server)
        assert opts.server_name == "livekit-server"
        assert opts.server_version == "1.0.0"

    @pytest.mark.asyncio
    async def test_list_rooms_has_no_required(self, server_and_module):
        server, _ = server_and_module
        handler = server.request_handlers[ListToolsRequest]
        result = await handler(None)
        list_rooms = next(t for t in result.root.tools if t.name == "list_rooms")
        assert list_rooms.inputSchema.get("required", []) == []

    @pytest.mark.asyncio
    async def test_tool_descriptions_are_present(self, server_and_module):
        server, _ = server_and_module
        handler = server.request_handlers[ListToolsRequest]
        result = await handler(None)
        for tool in result.root.tools:
            assert tool.description, f"Tool '{tool.name}' has no description"


class TestCredentials:
    @pytest.mark.asyncio
    async def test_missing_credentials_returns_error(self, server_and_module):
        server, _ = server_and_module
        import mcp.types as types

        handler = server.request_handlers[types.CallToolRequest]
        result = await handler(
            types.CallToolRequest(
                method="tools/call",
                params=types.CallToolRequestParams(
                    name="list_rooms",
                    arguments={},
                ),
            )
        )
        text = json.loads(result.root.content[0].text)
        assert "error" in text


class _call_tool:
    """Helper to call a tool on the server through its MCP handler."""

    @staticmethod
    async def do(server, tool_name, arguments):
        import mcp.types as types

        handler = server.request_handlers[types.CallToolRequest]
        return await handler(
            types.CallToolRequest(
                method="tools/call",
                params=types.CallToolRequestParams(
                    name=tool_name,
                    arguments=arguments,
                ),
            )
        )


class TestLiveKitAPI:
    @pytest.mark.asyncio
    async def test_create_room_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        mock_room_service = mocker.AsyncMock()
        mock_room_service.create_room = mocker.AsyncMock()
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.room = mock_room_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        await _call_tool.do(server, "create_room", {"name": "test-room"})
        mock_room_service.create_room.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_rooms_calls_api(self, mocker, set_env_creds, server_and_module):
        server, mod = server_and_module

        from livekit.api.room_service import ListRoomsResponse, Room

        resp = ListRoomsResponse()
        r = Room()
        r.name = "room-1"
        r.sid = "RM_test"
        resp.rooms.extend([r])

        mock_room_service = mocker.AsyncMock()
        mock_room_service.list_rooms = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.room = mock_room_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(server, "list_rooms", {})
        mock_room_service.list_rooms.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert "rooms" in text
        assert len(text["rooms"]) == 1

    @pytest.mark.asyncio
    async def test_generate_join_token(self, mocker, set_env_creds, server_and_module):
        server, mod = server_and_module

        mock_token = mocker.MagicMock()
        mock_token.to_jwt.return_value = "fake-jwt-token"
        mocker.patch.object(mod, "AccessToken", return_value=mock_token)

        result = await _call_tool.do(
            server,
            "generate_join_token",
            {"room": "my-room", "identity": "user-1"},
        )
        text = json.loads(result.root.content[0].text)
        assert text["token"] == "fake-jwt-token"
        assert text["room"] == "my-room"

    @pytest.mark.asyncio
    async def test_generate_join_token_with_grants(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        mock_token = mocker.MagicMock()
        mock_token.to_jwt.return_value = "fake-jwt-token"
        mocker.patch.object(mod, "AccessToken", return_value=mock_token)

        mock_vg = mocker.patch.object(
            mod, "VideoGrants", return_value=mocker.MagicMock()
        )

        await _call_tool.do(
            server,
            "generate_join_token",
            {
                "room": "my-room",
                "identity": "user-1",
                "can_publish": False,
                "can_subscribe": True,
                "can_publish_data": False,
                "room_admin": True,
                "ingress_admin": True,
                "agent": True,
            },
        )

        mock_vg.assert_called_once_with(
            room_join=True,
            room="my-room",
            can_publish=False,
            can_subscribe=True,
            can_publish_data=False,
            room_admin=True,
            ingress_admin=True,
            agent=True,
        )

    @pytest.mark.asyncio
    async def test_delete_room_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api.room_service import DeleteRoomResponse

        resp = DeleteRoomResponse()

        mock_room_service = mocker.AsyncMock()
        mock_room_service.delete_room = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.room = mock_room_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(server, "delete_room", {"room": "test-room"})
        mock_room_service.delete_room.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_list_participants_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api.room_service import ListParticipantsResponse, ParticipantInfo

        resp = ListParticipantsResponse()
        p = ParticipantInfo()
        p.identity = "user-1"
        resp.participants.extend([p])

        mock_room_service = mocker.AsyncMock()
        mock_room_service.list_participants = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.room = mock_room_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(server, "list_participants", {"room": "test-room"})
        text = json.loads(result.root.content[0].text)
        assert "participants" in text
        assert len(text["participants"]) == 1

    @pytest.mark.asyncio
    async def test_get_participant_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api.room_service import ParticipantInfo

        p = ParticipantInfo()
        p.identity = "user-1"

        mock_room_service = mocker.AsyncMock()
        mock_room_service.get_participant = mocker.AsyncMock(return_value=p)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.room = mock_room_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "get_participant",
            {"room": "test-room", "identity": "user-1"},
        )
        text = json.loads(result.root.content[0].text)
        assert text["identity"] == "user-1"

    @pytest.mark.asyncio
    async def test_remove_participant_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        mock_room_service = mocker.AsyncMock()
        mock_room_service.remove_participant = mocker.AsyncMock()
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.room = mock_room_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "remove_participant",
            {"room": "test-room", "identity": "user-1"},
        )
        text = json.loads(result.root.content[0].text)
        assert text["status"] == "removed"

    @pytest.mark.asyncio
    async def test_mute_participant_track_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api.room_service import MuteRoomTrackResponse

        resp = MuteRoomTrackResponse()

        mock_room_service = mocker.AsyncMock()
        mock_room_service.mute_published_track = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.room = mock_room_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "mute_participant_track",
            {
                "room": "test-room",
                "identity": "user-1",
                "track_sid": "TR_test",
                "muted": True,
            },
        )
        text = json.loads(result.root.content[0].text)
        assert text is not None

    @pytest.mark.asyncio
    async def test_update_participant_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api.room_service import ParticipantInfo

        p = ParticipantInfo()
        p.identity = "user-1"

        mock_room_service = mocker.AsyncMock()
        mock_room_service.update_participant = mocker.AsyncMock(return_value=p)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.room = mock_room_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "update_participant",
            {
                "room": "test-room",
                "identity": "user-1",
                "metadata": '{"role": "moderator"}',
            },
        )
        text = json.loads(result.root.content[0].text)
        assert text["identity"] == "user-1"

    @pytest.mark.asyncio
    async def test_update_room_metadata_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api.room_service import Room

        resp = Room()
        resp.name = "test-room"

        mock_room_service = mocker.AsyncMock()
        mock_room_service.update_room_metadata = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.room = mock_room_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "update_room_metadata",
            {"room": "test-room", "metadata": '{"key": "value"}'},
        )
        mock_room_service.update_room_metadata.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["name"] == "test-room"


class TestAPIErrors:
    @pytest.mark.asyncio
    async def test_api_error_returns_sanitized_message(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        mock_room_service = mocker.AsyncMock()
        mock_room_service.list_rooms = mocker.AsyncMock(
            side_effect=Exception("Internal server error: sensitive detail")
        )
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.room = mock_room_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(server, "list_rooms", {})
        text = json.loads(result.root.content[0].text)
        assert "error" in text
        assert "LiveKit API error:" in text["error"]

    @pytest.mark.asyncio
    async def test_missing_credentials_sanitized(self, server_and_module):
        server, _ = server_and_module
        import mcp.types as types

        handler = server.request_handlers[types.CallToolRequest]
        result = await handler(
            types.CallToolRequest(
                method="tools/call",
                params=types.CallToolRequestParams(
                    name="list_rooms",
                    arguments={},
                ),
            )
        )
        text = json.loads(result.root.content[0].text)
        assert "error" in text
        assert "user" not in text["error"].lower()


@pytest.mark.parametrize("test_config", TOOL_TESTS, ids=get_test_id)
@pytest.mark.asyncio
async def test_livekit_tool(client, context, test_config):
    return await run_tool_test(client, context, test_config)


class TestLiveIntegration:
    @pytest.mark.skipif(
        not os.environ.get("LIVEKIT_URL"),
        reason="LIVEKIT_URL not set; skipping live integration test",
    )
    @pytest.mark.asyncio
    async def test_room_lifecycle(self, client):
        response = await client.process_query(
            "Use the list_rooms tool to list all LiveKit rooms. "
            "If successful, start your response with 'Rooms found' or 'No rooms found' "
            "and include the count of rooms."
        )
        assert response, "No response from list_rooms"

    @pytest.mark.skipif(
        not os.environ.get("LIVEKIT_URL"),
        reason="LIVEKIT_URL not set; skipping live integration test",
    )
    @pytest.mark.asyncio
    async def test_create_and_delete_room(self, client):
        response = await client.process_query(
            "Use the create_room tool to create a new room named 'pfmcp-test-room'. "
            "If successful, start your response with 'Room created' and include the room name. "
            "Then use the delete_room tool to delete the 'pfmcp-test-room' room. "
            "If successful, start your response with 'Room deleted'."
        )
        assert response, "No response from create/delete room"
