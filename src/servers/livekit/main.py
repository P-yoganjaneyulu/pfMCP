import os
import sys
import json
import logging
from datetime import timedelta
from pathlib import Path

project_root = os.path.abspath(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

from mcp.types import TextContent, Tool, ImageContent, EmbeddedResource
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from src.utils.livekit.util import get_livekit_credentials

from livekit.api import LiveKitAPI, AccessToken, VideoGrants
from livekit.api.room_service import (
    CreateRoomRequest,
    DeleteRoomRequest,
    ListRoomsRequest,
    ListParticipantsRequest,
    RoomParticipantIdentity,
    UpdateParticipantRequest,
    MuteRoomTrackRequest,
    UpdateRoomMetadataRequest,
)
from google.protobuf.json_format import MessageToDict

SERVICE_NAME = Path(__file__).parent.name

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(SERVICE_NAME)


def _proto_to_dict(msg):
    return MessageToDict(msg, preserving_proto_field_name=True)


async def _create_api(user_id, api_key=None):
    url, key, secret = await get_livekit_credentials(user_id, api_key=api_key)
    return LiveKitAPI(url, key, secret)


def create_server(user_id, api_key=None):
    server = Server("livekit-server")
    server.user_id = user_id
    server.api_key = api_key

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        logger.info(f"Listing tools for user: {server.user_id}")
        return [
            Tool(
                name="create_room",
                description="Create a new LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Room name (must be unique within the project)",
                        },
                        "empty_timeout": {
                            "type": "integer",
                            "description": "Seconds before the room is closed after the last participant leaves (default: 300)",
                        },
                        "max_participants": {
                            "type": "integer",
                            "description": "Maximum number of participants allowed in the room",
                        },
                        "metadata": {
                            "type": "string",
                            "description": "JSON-encoded metadata for the room",
                        },
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="delete_room",
                description="Delete a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Name of the room to delete",
                        },
                    },
                    "required": ["room"],
                },
            ),
            Tool(
                name="list_rooms",
                description="List all LiveKit rooms",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of room names to filter by",
                        },
                    },
                },
            ),
            Tool(
                name="generate_join_token",
                description="Generate a JWT token for joining a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name the token grants access to",
                        },
                        "identity": {
                            "type": "string",
                            "description": "Unique identity for the participant",
                        },
                        "name": {
                            "type": "string",
                            "description": "Display name for the participant",
                        },
                        "metadata": {
                            "type": "string",
                            "description": "JSON-encoded metadata for the participant",
                        },
                        "ttl": {
                            "type": "integer",
                            "description": "Token time-to-live in seconds (default: 300)",
                        },
                        "can_publish": {
                            "type": "boolean",
                            "description": "Allowed to publish audio/video tracks (default: true)",
                        },
                        "can_subscribe": {
                            "type": "boolean",
                            "description": "Allowed to subscribe to tracks (default: true)",
                        },
                        "can_publish_data": {
                            "type": "boolean",
                            "description": "Allowed to publish data messages (default: true)",
                        },
                        "room_admin": {
                            "type": "boolean",
                            "description": "Grant room admin privileges (default: false)",
                        },
                        "ingress_admin": {
                            "type": "boolean",
                            "description": "Grant ingress admin privileges (default: false)",
                        },
                        "agent": {
                            "type": "boolean",
                            "description": "Allow this participant to act as an Agent worker (default: false)",
                        },
                    },
                    "required": ["room", "identity"],
                },
            ),
            Tool(
                name="list_participants",
                description="List participants in a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name",
                        },
                    },
                    "required": ["room"],
                },
            ),
            Tool(
                name="get_participant",
                description="Get details about a specific participant in a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name",
                        },
                        "identity": {
                            "type": "string",
                            "description": "Identity of the participant",
                        },
                    },
                    "required": ["room", "identity"],
                },
            ),
            Tool(
                name="update_participant",
                description="Update metadata or permissions for a participant in a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name",
                        },
                        "identity": {
                            "type": "string",
                            "description": "Identity of the participant to update",
                        },
                        "metadata": {
                            "type": "string",
                            "description": "New JSON-encoded metadata for the participant",
                        },
                        "name": {
                            "type": "string",
                            "description": "New display name for the participant",
                        },
                        "attributes": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                            "description": "Key-value attributes to set on the participant",
                        },
                    },
                    "required": ["room", "identity"],
                },
            ),
            Tool(
                name="remove_participant",
                description="Remove a participant from a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name",
                        },
                        "identity": {
                            "type": "string",
                            "description": "Identity of the participant to remove",
                        },
                    },
                    "required": ["room", "identity"],
                },
            ),
            Tool(
                name="mute_participant_track",
                description="Mute or unmute a specific track of a participant in a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name",
                        },
                        "identity": {
                            "type": "string",
                            "description": "Identity of the participant",
                        },
                        "track_sid": {
                            "type": "string",
                            "description": "SID of the track to mute/unmute",
                        },
                        "muted": {
                            "type": "boolean",
                            "description": "True to mute the track, False to unmute",
                        },
                    },
                    "required": ["room", "identity", "track_sid", "muted"],
                },
            ),
            Tool(
                name="update_room_metadata",
                description="Update metadata for a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name",
                        },
                        "metadata": {
                            "type": "string",
                            "description": "New JSON-encoded metadata for the room",
                        },
                    },
                    "required": ["room", "metadata"],
                },
            ),
        ]

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict | None
    ) -> list[TextContent | ImageContent | EmbeddedResource]:
        logger.info(
            f"User {server.user_id} calling tool: {name} with arguments: {arguments}"
        )

        if arguments is None:
            arguments = {}

        try:
            api = await _create_api(server.user_id, api_key=server.api_key)
        except ValueError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

        async with api as lk:
            try:
                if name == "create_room":
                    return await _handle_create_room(lk, arguments)
                elif name == "delete_room":
                    return await _handle_delete_room(lk, arguments)
                elif name == "list_rooms":
                    return await _handle_list_rooms(lk, arguments)
                elif name == "generate_join_token":
                    return await _handle_generate_join_token(arguments)
                elif name == "list_participants":
                    return await _handle_list_participants(lk, arguments)
                elif name == "get_participant":
                    return await _handle_get_participant(lk, arguments)
                elif name == "update_participant":
                    return await _handle_update_participant(lk, arguments)
                elif name == "remove_participant":
                    return await _handle_remove_participant(lk, arguments)
                elif name == "mute_participant_track":
                    return await _handle_mute_participant_track(lk, arguments)
                elif name == "update_room_metadata":
                    return await _handle_update_room_metadata(lk, arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error(f"Error calling LiveKit API for tool {name}: {e}")
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": f"LiveKit API error: {str(e)}"}),
                    )
                ]

    return server


async def _handle_create_room(lk, args):
    req = CreateRoomRequest(name=args["name"])
    if "empty_timeout" in args:
        req.empty_timeout = args["empty_timeout"]
    if "max_participants" in args:
        req.max_participants = args["max_participants"]
    if "metadata" in args:
        req.metadata = args["metadata"]

    result = await lk.room.create_room(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_delete_room(lk, args):
    req = DeleteRoomRequest(room=args["room"])
    await lk.room.delete_room(req)
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "status": "deleted",
                    "room": args["room"],
                },
                indent=2,
            ),
        )
    ]


async def _handle_list_rooms(lk, args):
    req = ListRoomsRequest()
    if "names" in args and args["names"]:
        req.names.extend(args["names"])

    result = await lk.room.list_rooms(req)
    rooms = [_proto_to_dict(r) for r in result.rooms]
    return [
        TextContent(
            type="text",
            text=json.dumps({"rooms": rooms}, indent=2),
        )
    ]


async def _handle_generate_join_token(args):
    url = os.environ.get("LIVEKIT_URL", "")
    api_key_val = os.environ.get("LIVEKIT_API_KEY", "")
    api_secret = os.environ.get("LIVEKIT_API_SECRET", "")

    if not api_key_val or not api_secret:
        auth_creds = await get_livekit_credentials("resolve", api_key=None)
        url, api_key_val, api_secret = auth_creds

    token = AccessToken(api_key_val, api_secret)
    token.with_identity(args["identity"])
    token.with_name(args.get("name", ""))
    token.with_metadata(args.get("metadata", ""))
    token.with_ttl(timedelta(seconds=min(args.get("ttl", 300), 86400)))

    grants = VideoGrants(
        room_join=True,
        room=args["room"],
        can_publish=args.get("can_publish", True),
        can_subscribe=args.get("can_subscribe", True),
        can_publish_data=args.get("can_publish_data", True),
        room_admin=args.get("room_admin", False),
        ingress_admin=args.get("ingress_admin", False),
        agent=args.get("agent", False),
    )
    token.with_grants(grants)

    jwt = token.to_jwt()
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "token": jwt,
                    "room": args["room"],
                    "identity": args["identity"],
                    "url": url,
                },
                indent=2,
            ),
        )
    ]


async def _handle_list_participants(lk, args):
    req = ListParticipantsRequest(room=args["room"])
    result = await lk.room.list_participants(req)
    participants = [_proto_to_dict(p) for p in result.participants]
    return [
        TextContent(
            type="text",
            text=json.dumps({"participants": participants}, indent=2),
        )
    ]


async def _handle_get_participant(lk, args):
    req = RoomParticipantIdentity(room=args["room"], identity=args["identity"])
    result = await lk.room.get_participant(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_update_participant(lk, args):
    req = UpdateParticipantRequest(room=args["room"], identity=args["identity"])
    if "metadata" in args:
        req.metadata = args["metadata"]
    if "name" in args:
        req.name = args["name"]
    if "attributes" in args and args["attributes"]:
        req.attributes.update(args["attributes"])

    result = await lk.room.update_participant(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_remove_participant(lk, args):
    req = RoomParticipantIdentity(room=args["room"], identity=args["identity"])
    await lk.room.remove_participant(req)
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "status": "removed",
                    "room": args["room"],
                    "identity": args["identity"],
                },
                indent=2,
            ),
        )
    ]


async def _handle_mute_participant_track(lk, args):
    req = MuteRoomTrackRequest(
        room=args["room"],
        identity=args["identity"],
        track_sid=args["track_sid"],
        muted=args["muted"],
    )
    result = await lk.room.mute_published_track(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_update_room_metadata(lk, args):
    req = UpdateRoomMetadataRequest(room=args["room"], metadata=args["metadata"])
    result = await lk.room.update_room_metadata(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


server = create_server


def get_initialization_options(server_instance: Server) -> InitializationOptions:
    return InitializationOptions(
        server_name="livekit-server",
        server_version="1.0.0",
        capabilities=server_instance.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )
