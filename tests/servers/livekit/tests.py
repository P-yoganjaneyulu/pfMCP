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
    {
        "name": "start_ingress",
        "args_template": 'with input_type="RTMP_INPUT" room_name="test-room"',
        "expected_keywords": ["ingress_id", "url"],
        "description": "create a new LiveKit ingress",
        "skip": True,
    },
    {
        "name": "list_ingress",
        "args_template": 'with room_name="test-room"',
        "expected_keywords": ["ingresses"],
        "description": "list all LiveKit ingresses",
        "skip": True,
    },
    {
        "name": "start_room_composite_egress",
        "args_template": 'with room_name="test-room" filepath="output.mp4"',
        "expected_keywords": ["egress_id"],
        "description": "start recording a room composite egress to file or stream",
        "skip": True,
    },
    {
        "name": "list_egress",
        "args_template": 'with room_name="test-room"',
        "expected_keywords": ["egresses"],
        "description": "list all LiveKit egresses",
        "skip": True,
    },
    {
        "name": "stop_egress",
        "args_template": 'with egress_id="EG_test"',
        "expected_keywords": ["egress_id"],
        "description": "stop a LiveKit egress",
        "skip": True,
    },
    {
        "name": "delete_ingress",
        "args_template": 'with ingress_id="ingress_test"',
        "expected_keywords": ["ingress_id"],
        "description": "delete a LiveKit ingress",
        "skip": True,
    },
    {
        "name": "update_layout",
        "args_template": 'with egress_id="EG_test" layout="speaker"',
        "expected_keywords": ["egress_id"],
        "description": "update the layout of an active room composite egress",
        "skip": True,
    },
    {
        "name": "update_ingress",
        "args_template": 'with ingress_id="ingress_test" room_name="test-room"',
        "expected_keywords": ["ingress_id"],
        "description": "update an existing LiveKit ingress",
        "skip": True,
    },
    {
        "name": "start_web_egress",
        "args_template": 'with url="https://example.com" filepath="output.mp4"',
        "expected_keywords": ["egress_id"],
        "description": "start recording a web page URL to file or stream",
        "skip": True,
    },
    {
        "name": "start_participant_egress",
        "args_template": 'with room_name="test-room" identity="user-1" filepath="output.mp4"',
        "expected_keywords": ["egress_id"],
        "description": "Start recording a specific participant in a room to file or stream",
        "skip": True,
    },
    {
        "name": "start_track_composite_egress",
        "args_template": 'with room_name="test-room" filepath="output.mp4"',
        "expected_keywords": ["egress_id"],
        "description": "Start recording a track composite egress to file or stream",
        "skip": True,
    },
    {
        "name": "start_track_egress",
        "args_template": 'with room_name="test-room" track_id="TR_test" filepath="output.mp4"',
        "expected_keywords": ["egress_id"],
        "description": "Start recording a specific track to file or websocket",
        "skip": True,
    },
    {
        "name": "update_stream",
        "args_template": 'with egress_id="EG_test" add_output_urls=["rtmp://example.com/stream"]',
        "expected_keywords": ["egress_id"],
        "description": "Add or remove stream URLs from an active egress",
        "skip": True,
    },
]

SHARED_CONTEXT = {}


@pytest.fixture(scope="module")
def context():
    return SHARED_CONTEXT


class TestToolDefinitions:
    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self, server_and_module):
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
            "start_ingress",
            "list_ingress",
            "start_room_composite_egress",
            "list_egress",
            "stop_egress",
            "delete_ingress",
            "update_layout",
            "update_ingress",
            "start_web_egress",
            "start_participant_egress",
            "start_track_composite_egress",
            "start_track_egress",
            "update_stream",
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
            "delete_room": set(),
            "list_participants": set(),
            "get_participant": {"identity"},
            "update_participant": {"identity"},
            "remove_participant": {"identity"},
            "mute_participant_track": {"identity", "track_sid", "muted"},
            "update_room_metadata": {"metadata"},
            "generate_join_token": {"identity"},
            "start_ingress": {"input_type"},
            "start_room_composite_egress": {"room_name"},
            "stop_egress": {"egress_id"},
            "delete_ingress": {"ingress_id"},
            "update_layout": {"egress_id", "layout"},
            "update_ingress": {"ingress_id"},
            "start_web_egress": {"url"},
            "start_participant_egress": {"room_name", "identity"},
            "start_track_composite_egress": {"room_name"},
            "start_track_egress": {"room_name", "track_id"},
            "update_stream": {"egress_id"},
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
        assert opts.server_version == "2.0.0"

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

    @pytest.mark.asyncio
    async def test_room_name_alias_has_anyOf_schema(self, server_and_module):
        server, _ = server_and_module
        handler = server.request_handlers[ListToolsRequest]
        result = await handler(None)
        alias_tools = {
            "delete_room", "list_participants", "get_participant",
            "update_participant", "remove_participant", "mute_participant_track",
            "update_room_metadata", "generate_join_token",
        }
        for tool in result.root.tools:
            if tool.name in alias_tools:
                any_of = tool.inputSchema.get("anyOf")
                assert any_of is not None, (
                    f"Tool '{tool.name}' missing anyOf for room/room_name"
                )
                assert len(any_of) == 2
                assert {"required": ["room"]} in any_of
                assert {"required": ["room_name"]} in any_of


class TestSecurityAndHelpers:
    def test_sanitize_error_redacts_access_key(self, server_and_module):
        _, mod = server_and_module
        result = mod._sanitize_error("access_key=AKIA12345")
        assert "[REDACTED]" in result
        assert "AKIA12345" not in result

    def test_sanitize_error_redacts_secret(self, server_and_module):
        _, mod = server_and_module
        result = mod._sanitize_error("secret=my-s3-secret")
        assert "[REDACTED]" in result
        assert "my-s3-secret" not in result

    def test_sanitize_error_redacts_api_key(self, server_and_module):
        _, mod = server_and_module
        result = mod._sanitize_error("api_key=sk-123456")
        assert "[REDACTED]" in result
        assert "sk-123456" not in result

    def test_sanitize_error_redacts_api_secret(self, server_and_module):
        _, mod = server_and_module
        result = mod._sanitize_error("api_secret: abc123def456")
        assert "[REDACTED]" in result
        assert "abc123def456" not in result

    def test_sanitize_error_redacts_account_key(self, server_and_module):
        _, mod = server_and_module
        result = mod._sanitize_error('"account_key": "az-key-789"')
        assert "[REDACTED]" in result
        assert "az-key-789" not in result

    def test_sanitize_error_redacts_credentials(self, server_and_module):
        _, mod = server_and_module
        result = mod._sanitize_error('"credentials": {"json": "key"}')
        assert "[REDACTED]" in result
        assert "json" not in result

    def test_sanitize_error_redacts_jwt_token(self, server_and_module):
        _, mod = server_and_module
        result = mod._sanitize_error("token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0")
        assert "[REDACTED]" in result
        assert "eyJhbGci" not in result

    def test_sanitize_error_redacts_private_key(self, server_and_module):
        _, mod = server_and_module
        result = mod._sanitize_error("private_key=-----BEGIN RSA PRIVATE KEY-----abc123")
        assert "[REDACTED]" in result
        assert "BEGIN RSA" not in result

    def test_sanitize_error_redacts_client_secret(self, server_and_module):
        _, mod = server_and_module
        result = mod._sanitize_error("client_secret: super-secret-client-value")
        assert "[REDACTED]" in result
        assert "super-secret-client-value" not in result

    def test_sanitize_error_redacts_bearer(self, server_and_module):
        _, mod = server_and_module
        result = mod._sanitize_error("bearer=eyJhbGciOiJIUzI1NiJ9")
        assert "[REDACTED]" in result
        assert "eyJhbGci" not in result

    def test_sanitize_error_redacts_refresh_token(self, server_and_module):
        _, mod = server_and_module
        result = mod._sanitize_error("refresh_token=rt_abc123def456")
        assert "[REDACTED]" in result
        assert "rt_abc123def456" not in result

    def test_sanitize_error_redacts_url_credentials(self, server_and_module):
        _, mod = server_and_module
        result = mod._sanitize_error("https://user:pass@livekit.example.com")
        assert "[REDACTED]" in result
        assert "user:pass" not in result

    def test_sanitize_error_leaves_clean_text(self, server_and_module):
        _, mod = server_and_module
        result = mod._sanitize_error("Normal error: room not found")
        assert result == "Normal error: room not found"

    def test_redact_args_removes_s3_keys(self, server_and_module):
        _, mod = server_and_module
        args = {
            "room_name": "test-room",
            "file_outputs": [
                {
                    "filepath": "output.mp4",
                    "s3": {"access_key": "AKIA123", "secret": "s3secret", "bucket": "my-bucket"},
                }
            ],
        }
        redacted = mod._redact_args(args)
        assert redacted["file_outputs"][0]["s3"]["access_key"] == "[REDACTED]"
        assert redacted["file_outputs"][0]["s3"]["secret"] == "[REDACTED]"
        assert redacted["file_outputs"][0]["s3"]["bucket"] == "my-bucket"
        assert redacted["room_name"] == "test-room"

    def test_redact_args_removes_azure_keys(self, server_and_module):
        _, mod = server_and_module
        args = {
            "file_outputs": [
                {
                    "azure": {"account_name": "myaccount", "account_key": "azkey123"},
                }
            ],
        }
        redacted = mod._redact_args(args)
        assert redacted["file_outputs"][0]["azure"]["account_key"] == "[REDACTED]"
        assert redacted["file_outputs"][0]["azure"]["account_name"] == "[REDACTED]"

    def test_redact_args_removes_gcp_credentials(self, server_and_module):
        _, mod = server_and_module
        args = {
            "file_outputs": [
                {
                    "gcp": {"credentials": '{"type":"service_account"}', "bucket": "my-bucket"},
                }
            ],
        }
        redacted = mod._redact_args(args)
        assert redacted["file_outputs"][0]["gcp"]["credentials"] == "[REDACTED]"
        assert redacted["file_outputs"][0]["gcp"]["bucket"] == "my-bucket"

    def test_redact_args_removes_alioss_keys(self, server_and_module):
        _, mod = server_and_module
        args = {
            "file_outputs": [
                {
                    "aliOSS": {"access_key": "AKID123", "secret": "ossSecret", "bucket": "my-bucket"},
                }
            ],
        }
        redacted = mod._redact_args(args)
        assert redacted["file_outputs"][0]["aliOSS"]["access_key"] == "[REDACTED]"
        assert redacted["file_outputs"][0]["aliOSS"]["secret"] == "[REDACTED]"
        assert redacted["file_outputs"][0]["aliOSS"]["bucket"] == "my-bucket"

    def test_redact_args_preserves_non_sensitive_args(self, server_and_module):
        _, mod = server_and_module
        args = {
            "room_name": "test-room",
            "identity": "user-1",
            "filepath": "output.mp4",
            "stream_urls": ["rtmp://example.com/stream"],
        }
        redacted = mod._redact_args(args)
        assert redacted == args

    def test_redact_args_handles_none(self, server_and_module):
        _, mod = server_and_module
        redacted = mod._redact_args(None)
        assert redacted is None

    def test_redact_args_removes_token_key(self, server_and_module):
        _, mod = server_and_module
        args = {"file_outputs": [{"token": "eyJhbGciOiJIUzI1NiJ9"}]}
        redacted = mod._redact_args(args)
        assert redacted["file_outputs"][0]["token"] == "[REDACTED]"

    def test_redact_args_removes_api_key_arg(self, server_and_module):
        _, mod = server_and_module
        args = {"file_outputs": [{"api_key": "sk-1234567890"}]}
        redacted = mod._redact_args(args)
        assert redacted["file_outputs"][0]["api_key"] == "[REDACTED]"

    def test_redact_args_removes_api_secret_arg(self, server_and_module):
        _, mod = server_and_module
        args = {"file_outputs": [{"api_secret": "my-api-secret-value"}]}
        redacted = mod._redact_args(args)
        assert redacted["file_outputs"][0]["api_secret"] == "[REDACTED]"

    def test_redact_args_removes_private_key_arg(self, server_and_module):
        _, mod = server_and_module
        args = {"file_outputs": [{"private_key": "-----BEGIN PRIVATE KEY-----"}]}
        redacted = mod._redact_args(args)
        assert redacted["file_outputs"][0]["private_key"] == "[REDACTED]"

    def test_resolve_room_name_uses_room(self, server_and_module):
        _, mod = server_and_module
        assert mod._resolve_room_name({"room": "my-room"}) == "my-room"

    def test_resolve_room_name_uses_room_name(self, server_and_module):
        _, mod = server_and_module
        assert mod._resolve_room_name({"room_name": "my-room"}) == "my-room"

    def test_resolve_room_name_room_name_wins_on_conflict(self, server_and_module):
        _, mod = server_and_module
        assert mod._resolve_room_name({"room": "room-a", "room_name": "room-b"}) == "room-b"

    def test_resolve_room_name_returns_none_if_neither(self, server_and_module):
        _, mod = server_and_module
        assert mod._resolve_room_name({}) is None

    def test_resolve_room_name_identity_if_same(self, server_and_module):
        _, mod = server_and_module
        assert mod._resolve_room_name({"room": "same", "room_name": "same"}) == "same"


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
    async def test_generate_join_token_with_room_name_alias(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        mock_token = mocker.MagicMock()
        mock_token.to_jwt.return_value = "fake-jwt-token"
        mocker.patch.object(mod, "AccessToken", return_value=mock_token)

        result = await _call_tool.do(
            server,
            "generate_join_token",
            {"room_name": "my-room", "identity": "user-1"},
        )
        text = json.loads(result.root.content[0].text)
        assert text["token"] == "fake-jwt-token"
        assert text["room"] == "my-room"

    @pytest.mark.asyncio
    async def test_generate_join_token_rejects_missing_room(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        result = await _call_tool.do(
            server,
            "generate_join_token",
            {"identity": "user-1"},
        )
        assert result.root.isError
        assert "validation error" in result.root.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_generate_join_token_uses_resolved_credentials(
        self, mocker, server_and_module
    ):
        server, mod = server_and_module

        mock_creds = ("https://resolved.url", "resolved-key", "resolved-secret")
        mocker.patch.object(mod, "get_livekit_credentials", return_value=mock_creds)

        mock_token = mocker.MagicMock()
        mock_token.to_jwt.return_value = "fake-jwt-token"
        mocker.patch.object(mod, "AccessToken", return_value=mock_token)

        result = await _call_tool.do(
            server,
            "generate_join_token",
            {"room": "test-room", "identity": "user-1"},
        )
        text = json.loads(result.root.content[0].text)
        assert text["url"] == "https://resolved.url"
        mod.get_livekit_credentials.assert_any_await("resolve", api_key=server.api_key)

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
    async def test_delete_room_with_room_name_alias(
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

        result = await _call_tool.do(server, "delete_room", {"room_name": "test-room"})
        mock_room_service.delete_room.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["room"] == "test-room"

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
    async def test_remove_participant_with_room_name_alias(
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
            {"room_name": "test-room", "identity": "user-1"},
        )
        mock_room_service.remove_participant.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["room"] == "test-room"

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
    async def test_mute_participant_track_with_room_name_alias(
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
            {"room_name": "test-room", "identity": "user-1", "track_sid": "TR_test", "muted": True},
        )
        mock_room_service.mute_published_track.assert_awaited_once()
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

    @pytest.mark.asyncio
    async def test_update_room_metadata_with_room_name_alias(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api.room_service import Room

        r = Room()
        r.name = "test-room"

        mock_room_service = mocker.AsyncMock()
        mock_room_service.update_room_metadata = mocker.AsyncMock(return_value=r)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.room = mock_room_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "update_room_metadata",
            {"room_name": "test-room", "metadata": '{"key": "value"}'},
        )
        mock_room_service.update_room_metadata.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["name"] == "test-room"

    @pytest.mark.asyncio
    async def test_start_ingress_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api import IngressInfo

        resp = IngressInfo()
        resp.ingress_id = "ingress_test"
        resp.url = "rtmp://example.com/live/stream"

        mock_ingress_service = mocker.AsyncMock()
        mock_ingress_service.create_ingress = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.ingress = mock_ingress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "start_ingress",
            {"input_type": "RTMP_INPUT", "room_name": "test-room"},
        )
        mock_ingress_service.create_ingress.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["ingress_id"] == "ingress_test"
        assert text["url"] == "rtmp://example.com/live/stream"

    @pytest.mark.asyncio
    async def test_list_ingress_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api import ListIngressResponse, IngressInfo

        resp = ListIngressResponse()
        item = IngressInfo()
        item.ingress_id = "ingress_test"
        resp.items.extend([item])

        mock_ingress_service = mocker.AsyncMock()
        mock_ingress_service.list_ingress = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.ingress = mock_ingress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(server, "list_ingress", {"room_name": "test-room"})
        mock_ingress_service.list_ingress.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert "ingresses" in text
        assert len(text["ingresses"]) == 1

    @pytest.mark.asyncio
    async def test_start_room_composite_egress_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api import EgressInfo

        resp = EgressInfo()
        resp.egress_id = "egress_test"

        mock_egress_service = mocker.AsyncMock()
        mock_egress_service.start_room_composite_egress = mocker.AsyncMock(
            return_value=resp
        )
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "start_room_composite_egress",
            {"room_name": "test-room", "filepath": "output.mp4"},
        )
        mock_egress_service.start_room_composite_egress.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["egress_id"] == "egress_test"

    @pytest.mark.asyncio
    async def test_list_egress_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api import ListEgressResponse, EgressInfo

        resp = ListEgressResponse()
        item = EgressInfo()
        item.egress_id = "egress_test"
        resp.items.extend([item])

        mock_egress_service = mocker.AsyncMock()
        mock_egress_service.list_egress = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(server, "list_egress", {"room_name": "test-room"})
        mock_egress_service.list_egress.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert "egresses" in text
        assert len(text["egresses"]) == 1

    @pytest.mark.asyncio
    async def test_stop_egress_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api import EgressInfo

        resp = EgressInfo()
        resp.egress_id = "egress_test"

        mock_egress_service = mocker.AsyncMock()
        mock_egress_service.stop_egress = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(server, "stop_egress", {"egress_id": "EG_test"})
        mock_egress_service.stop_egress.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["egress_id"] == "egress_test"

    @pytest.mark.asyncio
    async def test_start_egress_audio_and_video_only_error(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        mock_egress_service = mocker.AsyncMock()
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "start_room_composite_egress",
            {
                "room_name": "test-room",
                "audio_only": True,
                "video_only": True,
                "filepath": "output.mp4",
            },
        )
        mock_egress_service.start_room_composite_egress.assert_not_called()
        text = json.loads(result.root.content[0].text)
        assert "error" in text

    @pytest.mark.asyncio
    async def test_start_egress_missing_output_error(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        mock_egress_service = mocker.AsyncMock()
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "start_room_composite_egress",
            {"room_name": "test-room"},
        )
        mock_egress_service.start_room_composite_egress.assert_not_called()
        text = json.loads(result.root.content[0].text)
        assert "error" in text

    @pytest.mark.asyncio
    async def test_delete_ingress_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api import IngressInfo

        resp = IngressInfo()
        resp.ingress_id = "ingress_test"

        mock_ingress_service = mocker.AsyncMock()
        mock_ingress_service.delete_ingress = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.ingress = mock_ingress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server, "delete_ingress", {"ingress_id": "ingress_test"}
        )
        mock_ingress_service.delete_ingress.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["ingress_id"] == "ingress_test"

    @pytest.mark.asyncio
    async def test_update_layout_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api import EgressInfo

        resp = EgressInfo()
        resp.egress_id = "egress_test"

        mock_egress_service = mocker.AsyncMock()
        mock_egress_service.update_layout = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "update_layout",
            {"egress_id": "EG_test", "layout": "speaker"},
        )
        mock_egress_service.update_layout.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["egress_id"] == "egress_test"

    @pytest.mark.asyncio
    async def test_update_ingress_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api import IngressInfo

        resp = IngressInfo()
        resp.ingress_id = "ingress_test"

        mock_ingress_service = mocker.AsyncMock()
        mock_ingress_service.update_ingress = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.ingress = mock_ingress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "update_ingress",
            {"ingress_id": "ingress_test", "room_name": "test-room"},
        )
        mock_ingress_service.update_ingress.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["ingress_id"] == "ingress_test"

    @pytest.mark.asyncio
    async def test_start_web_egress_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api import EgressInfo

        resp = EgressInfo()
        resp.egress_id = "egress_test"

        mock_egress_service = mocker.AsyncMock()
        mock_egress_service.start_web_egress = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "start_web_egress",
            {"url": "https://example.com", "filepath": "output.mp4"},
        )
        mock_egress_service.start_web_egress.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["egress_id"] == "egress_test"

    @pytest.mark.asyncio
    async def test_start_participant_egress_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api import EgressInfo

        resp = EgressInfo()
        resp.egress_id = "egress_test"

        mock_egress_service = mocker.AsyncMock()
        mock_egress_service.start_participant_egress = mocker.AsyncMock(
            return_value=resp
        )
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "start_participant_egress",
            {"room_name": "test-room", "identity": "user-1", "filepath": "output.mp4"},
        )
        mock_egress_service.start_participant_egress.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["egress_id"] == "egress_test"

    @pytest.mark.asyncio
    async def test_start_track_composite_egress_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api import EgressInfo

        resp = EgressInfo()
        resp.egress_id = "egress_test"

        mock_egress_service = mocker.AsyncMock()
        mock_egress_service.start_track_composite_egress = mocker.AsyncMock(
            return_value=resp
        )
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "start_track_composite_egress",
            {"room_name": "test-room", "filepath": "output.mp4"},
        )
        mock_egress_service.start_track_composite_egress.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["egress_id"] == "egress_test"

    @pytest.mark.asyncio
    async def test_start_track_egress_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api import EgressInfo

        resp = EgressInfo()
        resp.egress_id = "egress_test"

        mock_egress_service = mocker.AsyncMock()
        mock_egress_service.start_track_egress = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "start_track_egress",
            {"room_name": "test-room", "track_id": "TR_test", "filepath": "output.mp4"},
        )
        mock_egress_service.start_track_egress.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["egress_id"] == "egress_test"

    @pytest.mark.asyncio
    async def test_update_stream_calls_api(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        from livekit.api import EgressInfo

        resp = EgressInfo()
        resp.egress_id = "egress_test"

        mock_egress_service = mocker.AsyncMock()
        mock_egress_service.update_stream = mocker.AsyncMock(return_value=resp)
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "update_stream",
            {
                "egress_id": "EG_test",
                "add_output_urls": ["rtmp://example.com/stream"],
            },
        )
        mock_egress_service.update_stream.assert_awaited_once()
        text = json.loads(result.root.content[0].text)
        assert text["egress_id"] == "egress_test"

    @pytest.mark.asyncio
    async def test_start_web_egress_audio_and_video_only_error(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        mock_egress_service = mocker.AsyncMock()
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "start_web_egress",
            {
                "url": "https://example.com",
                "audio_only": True,
                "video_only": True,
                "filepath": "output.mp4",
            },
        )
        mock_egress_service.start_web_egress.assert_not_called()
        text = json.loads(result.root.content[0].text)
        assert "error" in text

    @pytest.mark.asyncio
    async def test_start_participant_egress_missing_output_error(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        mock_egress_service = mocker.AsyncMock()
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "start_participant_egress",
            {"room_name": "test-room", "identity": "user-1"},
        )
        mock_egress_service.start_participant_egress.assert_not_called()
        text = json.loads(result.root.content[0].text)
        assert "error" in text

    @pytest.mark.asyncio
    async def test_start_track_composite_egress_missing_output_error(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        mock_egress_service = mocker.AsyncMock()
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "start_track_composite_egress",
            {"room_name": "test-room"},
        )
        mock_egress_service.start_track_composite_egress.assert_not_called()
        text = json.loads(result.root.content[0].text)
        assert "error" in text

    @pytest.mark.asyncio
    async def test_start_track_egress_missing_output_error(
        self, mocker, set_env_creds, server_and_module
    ):
        server, mod = server_and_module

        mock_egress_service = mocker.AsyncMock()
        mock_api = mocker.AsyncMock(spec=mod.LiveKitAPI)
        mock_api.__aenter__.return_value = mock_api
        mock_api.egress = mock_egress_service

        mocker.patch.object(mod, "_create_api", return_value=mock_api)

        result = await _call_tool.do(
            server,
            "start_track_egress",
            {"room_name": "test-room", "track_id": "TR_test"},
        )
        mock_egress_service.start_track_egress.assert_not_called()
        text = json.loads(result.root.content[0].text)
        assert "error" in text


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
